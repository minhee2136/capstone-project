import re
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import gurobipy as gp
from gurobipy import GRB
from artifacts.models import Artifact
from django.conf import settings

# Zone Map settings
ZONE_MAP = {
    "201":"South","202":"South","203":"South","203A":"South","203B":"South",
    "204":"South","205":"South","206":"South","207":"South","208":"South",
    "209":"South","210":"South","210A":"South","211":"South",
    "212":"South","213":"South","214":"South","215":"South",
    "216":"South","216B":"South","217":"South",
    "218":"East","219":"East","220":"East","221":"East","222":"East",
    "223":"East","224":"East","224A":"East","224B":"East",
    "225":"East","226":"East","226A":"East","227":"East",
    "228":"East","228B":"East","229":"East","230":"East",
    "231":"North","232":"North","233":"North","234":"North",
    "235":"North","235A":"North","235B":"North","236":"North","237":"North",
    "238":"West","239":"West","240":"West","241":"West",
    "241A":"West","241C":"West",
    "242":"West","242B":"West","243":"West","244":"West",
}

def get_loc(s):
    s = str(s).strip()
    m = re.match(r"(\d+)([A-Z]*)", s)
    if not m: return (1, "All")
    num, rid = int(m.group(1)), m.group(1)+m.group(2)
    return (1, "All") if num < 200 else (2, ZONE_MAP.get(rid, "?"))

def move_min(l1, l2):
    f1, z1 = l1; f2, z2 = l2
    if l1 == l2: return 0.0
    if f1 != f2: return 1.0
    if f1 == 1:  return 0.5
    if z1 == z2: return 0.5
    return 1.0


def calculate_optimal_path(
    user_interest: str,
    t_total: int = 60,
    t_min_ratio: float = 2/3,
    start_idx: int = 0,
    history: list = None,
    top_n: int = 50,
    top_edges: int = 10,
    embed_model_name: str = "distiluse-base-multilingual-cased-v1",
    gurobi_timelimit: int = 120,
    alpha: float = 1.0,
    beta: float = 0.005
):
    if history is None:
        history = []
        
    T = t_total
    T_min = t_min_ratio * T
    VIEW = 4
    
    # 1. DB에서 데이터 로드 (엑셀 대신)
    # 실제로는 is_active=True 등 필터링이 필요할 수 있습니다.
    artifacts = list(Artifact.objects.exclude(embedding_vector__isnull=True).exclude(embedding_vector=""))
    if not artifacts:
        return {"error": "DB에 임베딩된 유물이 없습니다."}
    
    # 벡터 추출
    # artifacts의 embedding_vector가 list[float] 형태라고 가정 (JSONField)
    # 만약 콤마로 된 문자열이라면 엑셀처럼 분리해야 합니다.
    try:
        if isinstance(artifacts[0].embedding_vector, str):
            emb_all = np.vstack([np.fromstring(a.embedding_vector, sep=",") for a in artifacts])
        else:
            emb_all = np.vstack([np.array(a.embedding_vector, dtype=np.float32) for a in artifacts])
    except Exception as e:
        return {"error": f"임베딩 벡터 변환 중 오류: {str(e)}"}

    model = SentenceTransformer(embed_model_name)
    emb_user = model.encode([user_interest])
    
    # 💥 차원 불일치(512 vs 384)가 발생하는 경우를 대비해, 
    # emb_all의 차원 수에 맞춰 emb_user 차원을 잘라 맞춰줌
    dim_target = emb_all.shape[1]
    if emb_user.shape[1] != dim_target:
        emb_user = emb_user[:, :dim_target]

    ci_raw = cosine_similarity(emb_user, emb_all)[0]
    
    # 상위 N개 추출
    top_idx = np.argsort(ci_raw)[::-1][:top_n]
    
    selected_artifacts = [artifacts[i] for i in top_idx]
    emb = emb_all[top_idx]
    ci_s = ci_raw[top_idx]
    N = len(selected_artifacts)
    
    # 0 나누기 방지를 위한 안전 정규화
    ci_range = ci_s.max() - ci_s.min() + 1e-9
    ci = (ci_s - ci_s.min()) / ci_range
    
    mij_r = cosine_similarity(emb)
    mij_range = mij_r.max() - mij_r.min() + 1e-9
    mij = (mij_r - mij_r.min()) / mij_range
    
    locs = [get_loc(art.current_location) for art in selected_artifacts]
    
    tij = np.zeros((N, N))
    for i in range(N):
        for j in range(N):
            if i != j:
                tij[i][j] = move_min(locs[i], locs[j]) + VIEW

    def reoptimize(Hi_session, T_remain, visited_ids_all):
        hi = np.zeros(N, dtype=int)
        
        # visited_ids_all은 selected_artifacts의 실제 cleveland_id 리스트
        past_idx = [i for i in range(N) if selected_artifacts[i].cleveland_id in visited_ids_all]
        for idx in past_idx + Hi_session:
            hi[idx] = 1

        s = Hi_session[-1] if Hi_session else start_idx
        hi[s] = 0

        Hi_global = Hi_session[:]
        T_safe_remain = T_remain

        if T_safe_remain <= 0:
            return None, 0

        edges_sub = []
        for i in range(N):
            if hi[i] and i != s: continue
            cands = sorted(
                [(j, mij[i][j]) for j in range(N)
                 if j != i and not hi[j] and tij[i][j] <= T_remain],
                key=lambda x: -x[1]
            )
            for j, _ in cands[:top_edges]:
                edges_sub.append((i, j))

        if not edges_sub:
            return None, 0

        out_e_sub = {i: [] for i in range(N)}
        in_e_sub  = {j: [] for j in range(N)}
        for (a, b) in edges_sub:
            out_e_sub[a].append(b)
            in_e_sub[b].append(a)

        in_e_sub[s] = []

        if not out_e_sub[s]:
            return None, 0

        mdl = gp.Model()
        mdl.setParam("OutputFlag", 0)
        mdl.setParam("TimeLimit", gurobi_timelimit)
        mdl.setParam("MIPGap", 0.01)

        x = mdl.addVars(N, vtype=GRB.BINARY)
        y = mdl.addVars(edges_sub, vtype=GRB.BINARY)

        term_interest = gp.quicksum(ci[i]*x[i] for i in range(N))
        term_context  = gp.quicksum(mij[i][j]*y[i,j] for (i,j) in edges_sub)
        term_history  = (
            gp.quicksum(
                (1.0 / len(Hi_global)) * mij[h][i] * x[i]
                for i in range(N)
                for h in Hi_global
            ) if Hi_global else gp.LinExpr(0)
        )

        mdl.setObjective(
            alpha * (term_interest + term_context + term_history)
            - beta * gp.quicksum(tij[i][j]*y[i,j] for (i,j) in edges_sub),
            GRB.MAXIMIZE
        )

        mdl.addConstr(
            gp.quicksum(tij[i][j]*y[i,j] for (i,j) in edges_sub) <= T_safe_remain,
            "T_upper"
        )
        mdl.addConstr(
            gp.quicksum(tij[i][j]*y[i,j] for (i,j) in edges_sub) >= T_min * (T_remain / T),
            "T_lower"
        )

        mdl.addConstr(x[s] == 1)
        mdl.addConstr(gp.quicksum(y[s,j] for j in out_e_sub[s]) == 1)

        for i in range(N):
            if out_e_sub[i]:
                mdl.addConstr(gp.quicksum(y[i,j] for j in out_e_sub[i]) <= 1)
        for j in range(N):
            if in_e_sub[j]:
                mdl.addConstr(gp.quicksum(y[i,j] for i in in_e_sub[j]) <= 1)

        for i in range(N):
            if i == s: continue
            if not in_e_sub[i]:
                mdl.addConstr(x[i] == 0); continue
            mdl.addConstr(x[i] == gp.quicksum(y[k,i] for k in in_e_sub[i]))
            if out_e_sub[i]:
                mdl.addConstr(gp.quicksum(y[i,j] for j in out_e_sub[i]) <= x[i])

        for i in range(N):
            if hi[i] and i != s:
                mdl.addConstr(x[i] == 0)

        mdl.optimize()

        if mdl.status not in [GRB.OPTIMAL, GRB.SUBOPTIMAL]:
            return None, 0

        selected = {i: j for (i,j) in edges_sub if y[i,j].X > 0.5}
        if s not in selected:
            return None, 0

        next_idx = selected[s]
        next_cost = tij[s][next_idx]
        return next_idx, next_cost

    Hi_session = [start_idx]
    T_remain = T
    total_t = 0.0
    
    # path_steps에 인덱스와 함께 이전 유물부터의 이동 시간(cost)을 저장 (시작점은 0)
    path_steps = [(start_idx, 0.0)]

    while T_remain > VIEW:
        n_idx, cost = reoptimize(Hi_session, T_remain, history)
        if n_idx is None:
            break
        path_steps.append((n_idx, cost))
        Hi_session.append(n_idx)
        T_remain -= cost
        total_t += cost

    final_path = []
    for i, (idx, cost) in enumerate(path_steps):
        artifact = selected_artifacts[idx]
        
        # 이전 위치 구하기 위한 로직
        prev_location = "입구"
        if i > 0:
            prev_location = selected_artifacts[path_steps[i-1][0]].current_location
            
        final_path.append({
            "artifact_id": artifact.cleveland_id,
            "title": artifact.title,
            "type": artifact.type,
            "current_location": artifact.current_location,
            "prev_location": prev_location,
            "image_url": artifact.image_url,
            "department": artifact.department,
            "step_time": round(cost, 1)  # 여기까지 오는 데 걸린 소요시간
        })
        
    return {
        "status": "success",
        "total_time_minutes": round(total_t, 1),
        "path_length": len(final_path),
        "path": final_path
    }
