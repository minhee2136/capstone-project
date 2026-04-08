import random
import re
import numpy as np
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from openai import OpenAI
from django.conf import settings
from sentence_transformers import SentenceTransformer
from groq import Groq

from sessions.models import Session
from artifacts.models import Artifact
from .models import Chat, Message, Feedback
from .serializers import MessageCreateSerializer, MessageSerializer, FeedbackCreateSerializer

embedding_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
groq_client = Groq(api_key=settings.GROQ_API_KEY)
GROQ_MODEL = "llama3-8b-8192"


def _groq_generate(prompt: str) -> str | None:
    """Groq LLM 호출. 실패 시 None 반환."""
    try:
        resp = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return None

CONN_MESSAGES = {
    "story":    "이전 작품과 같은 흐름으로 이어지는 작품이에요.",
    "mystery":  "전혀 다를 것 같지만, 의외의 연결이 있어요.",
    "contrast": "취향을 반영해서 방향을 바꿔볼게요.",
    "shock":    "지나치기 아쉬운 작품이 근처에 있어요.",
}


def _get_chat_or_404(chat_id):
    try:
        return Chat.objects.select_related('session').get(id=chat_id), None
    except Chat.DoesNotExist:
        return None, Response({'error': '채팅을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)


def _decide_conn_type(similarity_score, feedback_history, history_count):
    recent = feedback_history[-2:]
    if any(f == -1 for f in recent):
        return "contrast"
    if history_count < 3:
        return "story"
    if similarity_score >= 0.85:
        return "mystery"
    if 0.6 <= similarity_score < 0.85:
        return "story"
    return "shock"


def _gallery_number(location: str) -> int:
    m = re.match(r'(\d+)', location.strip())
    return int(m.group(1)) if m else -1


def _cosine_scores(query_vec, candidates):
    scored = []
    for artifact in candidates:
        vec = np.array(artifact.embedding_vector, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm == 0:
            continue
        score = float(np.dot(query_vec, vec / norm))
        scored.append((score, artifact))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


class ChatMessageView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/chat/{session_id}/messages/ — 채팅 메시지 전송",
        request_body=MessageCreateSerializer,
        responses={201: "메시지 전송 성공"},
    )
    def post(self, request, session_id):
        session = get_object_or_404(Session, id=session_id)
        serializer = MessageCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_message = serializer.validated_data['message']

        # 사용자 메시지 저장
        Message.objects.create(
            session=session,
            role=Message.Role.USER,
            content=user_message,
        )

        # 이전 대화 히스토리 조회
        history = Message.objects.filter(session=session).order_by('created_at')
        gpt_messages = [
            {
                "role": "system",
                "content": (
                    f"당신은 뮤지엄 큐레이터입니다. "
                    f"사용자의 관심사: {session.interest_tags}, "
                    f"지식 수준: {session.knowledge_level}, "
                    f"관람 희망 시간: {session.view_time_minutes}분. "
                    f"사용자 맞춤형 유물을 추천하고 설명해주세요."
                )
            }
        ]
        for msg in history:
            gpt_messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        # GPT-4o-mini 호출
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        gpt_response = client.chat.completions.create(
            model=settings.GPT_MODEL,
            messages=gpt_messages,
        )
        assistant_content = gpt_response.choices[0].message.content

        # 어시스턴트 메시지 저장
        assistant_message = Message.objects.create(
            session=session,
            role=Message.Role.ASSISTANT,
            content=assistant_content,
        )

        return Response(
            {
                'message_id': assistant_message.id,
                'role': assistant_message.role,
                'content': assistant_message.content,
                'artifact': None,
                'created_at': assistant_message.created_at,
            },
            status=status.HTTP_201_CREATED,
        )

    @swagger_auto_schema(
        operation_description="GET /api/chat/{session_id}/messages/ — 채팅 히스토리 조회",
        responses={200: "채팅 히스토리 조회 성공"},
    )
    def get(self, request, session_id):
        session = get_object_or_404(Session, id=session_id)
        messages = Message.objects.filter(session=session).order_by('created_at')
        serializer = MessageSerializer(messages, many=True)
        return Response({'messages': serializer.data})


class FeedbackView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/recommendations/{rec_id}/feedback/ — 피드백 제출",
        request_body=FeedbackCreateSerializer,
        responses={201: "피드백 제출 성공"},
    )
    def post(self, request, rec_id):
        session = get_object_or_404(Session, id=request.data.get('session_id'))
        serializer = FeedbackCreateSerializer(data=request.data)

        if serializer.is_valid():
            feedback = Feedback.objects.create(
                session=session,
                artifact_id=rec_id,
                feedback_type=serializer.validated_data['feedback_type'],
            )
            return Response(
                FeedbackCreateSerializer(feedback).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ── Chat 기반 API ──────────────────────────────────────────────────────────────

class ChatCreateView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/chats/ — 채팅 생성",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['session_id'],
            properties={'session_id': openapi.Schema(type=openapi.TYPE_INTEGER)},
        ),
        responses={201: openapi.Response('채팅 생성 성공', schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'chat_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'session_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'created_at': openapi.Schema(type=openapi.TYPE_STRING),
            },
        ))},
    )
    def post(self, request):
        session = get_object_or_404(Session, id=request.data.get('session_id'))
        chat = Chat.objects.create(session=session)
        return Response(
            {
                'chat_id': chat.id,
                'session_id': chat.session_id,
                'created_at': chat.created_at.isoformat().replace('+00:00', 'Z'),
            },
            status=status.HTTP_201_CREATED,
        )


class ChatRecommendationsView(generics.RetrieveAPIView):

    @swagger_auto_schema(
        operation_description="GET /api/chats/{chat_id}/recommendations/ — 유물 추천 (상위 5개)",
        responses={
            200: openapi.Response('추천 목록', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'chat_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'recommendations': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                },
            )),
            400: '임베딩 생성 불가',
            404: '채팅 없음',
        },
    )
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def retrieve(self, _request, *_args, **_kwargs):
        chat_id = self.kwargs['chat_id']
        chat, err = _get_chat_or_404(chat_id)
        if err:
            return err

        session = chat.session
        interest_keywords = session.interest_tags or []
        interest_tag = session.interest_tag

        if interest_keywords:
            candidate_qs = Artifact.objects.filter(
                keyword__in=interest_keywords,
                embedding_vector__isnull=False,
            )
        else:
            candidate_qs = Artifact.objects.filter(embedding_vector__isnull=False)

        viewed_ids = set(chat.history)
        candidates = [a for a in candidate_qs if a.id not in viewed_ids]

        if not candidates:
            return Response({'chat_id': chat_id, 'recommendations': []})

        if interest_tag:
            query_vec = embedding_model.encode(interest_tag).astype(np.float32)
        else:
            vecs = np.array([a.embedding_vector for a in candidates], dtype=np.float32)
            query_vec = vecs.mean(axis=0)

        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return Response({'error': '쿼리 벡터가 zero vector입니다.'}, status=status.HTTP_400_BAD_REQUEST)
        query_vec = query_vec / query_norm

        scored = _cosine_scores(query_vec, candidates)
        recommendations = [
            {
                'artifact_id': a.cleveland_id,
                'title': a.title,
                'type': a.type,
                'current_location': a.current_location,
                'image_url': a.image_url,
                'similarity_score': round(score, 4),
            }
            for score, a in scored[:5]
        ]
        return Response({'chat_id': chat_id, 'recommendations': recommendations})


class ChatFeedbackView(generics.CreateAPIView):

    @swagger_auto_schema(
        operation_description="POST /api/chats/{chat_id}/feedback/ — 유물 피드백 (1: 흥미로워요, -1: 별로예요)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['artifact_id', 'feedback'],
            properties={
                'artifact_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'feedback': openapi.Schema(type=openapi.TYPE_INTEGER, description='1 또는 -1'),
            },
        ),
        responses={
            201: openapi.Response('피드백 저장 성공', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'chat_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'artifact_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'feedback': openapi.Schema(type=openapi.TYPE_INTEGER),
                },
            )),
            400: '유효하지 않은 요청',
            404: '채팅 없음',
        },
    )
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def create(self, request, *_args, **_kwargs):
        chat_id = self.kwargs['chat_id']
        chat, err = _get_chat_or_404(chat_id)
        if err:
            return err

        artifact_id = request.data.get('artifact_id')
        feedback_int = request.data.get('feedback')

        if feedback_int not in (1, -1):
            return Response({'error': 'feedback은 1 또는 -1이어야 합니다.'}, status=status.HTTP_400_BAD_REQUEST)
        if not Artifact.objects.filter(cleveland_id=artifact_id).exists():
            return Response({'error': '존재하지 않는 artifact_id입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        chat.feedback_history = list(chat.feedback_history) + [feedback_int]
        chat.save(update_fields=['feedback_history'])

        return Response(
            {'chat_id': chat_id, 'artifact_id': artifact_id, 'feedback': feedback_int},
            status=status.HTTP_201_CREATED,
        )


class ChatNextRecommendationView(generics.RetrieveAPIView):

    @swagger_auto_schema(
        operation_description="GET /api/chats/{chat_id}/next-recommendation/ — 다음 유물 추천",
        responses={
            200: openapi.Response('다음 추천 유물', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'chat_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'artifact': openapi.Schema(type=openapi.TYPE_OBJECT),
                    'conn_type': openapi.Schema(type=openapi.TYPE_STRING),
                    'conn_message': openapi.Schema(type=openapi.TYPE_STRING),
                },
            )),
            400: '히스토리 없음 또는 임베딩 없음',
            404: '채팅 없음',
        },
    )
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def retrieve(self, _request, *_args, **_kwargs):
        chat_id = self.kwargs['chat_id']
        chat, err = _get_chat_or_404(chat_id)
        if err:
            return err

        if not chat.history:
            return Response(
                {'error': '관람 히스토리가 없습니다. 먼저 유물을 관람해주세요.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        viewed_artifacts = Artifact.objects.filter(id__in=chat.history, embedding_vector__isnull=False)
        history_vecs = [a.embedding_vector for a in viewed_artifacts]

        if not history_vecs:
            return Response({'error': '히스토리 유물에 임베딩 벡터가 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        query_vec = np.array(history_vecs, dtype=np.float32).mean(axis=0)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return Response({'error': '쿼리 벡터가 zero vector입니다.'}, status=status.HTTP_400_BAD_REQUEST)
        query_vec = query_vec / query_norm

        viewed_ids = set(chat.history)
        candidates = [
            a for a in Artifact.objects.filter(embedding_vector__isnull=False)
            if a.id not in viewed_ids
        ]
        if not candidates:
            return Response({'error': '추천 가능한 유물이 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        scored = _cosine_scores(query_vec, candidates)
        conn_type = _decide_conn_type(scored[0][0], list(chat.feedback_history), len(chat.history))

        if conn_type == "story":
            chosen_score, chosen = scored[0]
        elif conn_type == "mystery":
            n = len(scored)
            lo, hi = max(0, int(n * 0.30)), max(1, int(n * 0.60))
            chosen_score, chosen = random.choice(scored[lo:hi])
        elif conn_type == "contrast":
            chosen_score, chosen = scored[-1]
        else:  # shock
            session_gallery = _gallery_number(chat.session.current_location or "")
            if session_gallery >= 0:
                scored.sort(key=lambda x: abs(_gallery_number(x[1].current_location) - session_gallery))
            chosen_score, chosen = scored[0]

        # ── conn_message: Groq LLM 생성, 실패 시 템플릿 fallback ──────────
        prev_artifact = None
        if chat.history:
            prev_artifacts = Artifact.objects.filter(id=list(chat.history)[-1])
            prev_artifact = prev_artifacts.first()

        if prev_artifact:
            prompt = (
                f"이전 유물: {prev_artifact.title}, {prev_artifact.type}, {prev_artifact.department}\n"
                f"다음 유물: {chosen.title}, {chosen.type}, {chosen.department}\n"
                f"연결 방식: {conn_type}\n\n"
                f"위 두 유물의 연결을 한국어로 1~2문장으로 자연스럽게 설명해줘.\n"
                f"유물명은 영어 그대로 써도 돼.\n"
                f"conn_type이 story면 흐름이 이어짐, mystery면 의외의 연결, "
                f"contrast면 대비, shock면 발길을 멈추게 하는 작품으로 설명해줘.\n"
                f"반드시 한국어로만 출력해줘."
            )
            conn_message = _groq_generate(prompt) or CONN_MESSAGES[conn_type]
        else:
            conn_message = CONN_MESSAGES[conn_type]

        chat.history = list(chat.history) + [chosen.id]
        chat.save(update_fields=['history'])

        return Response({
            'chat_id': chat_id,
            'artifact': {
                'artifact_id': chosen.cleveland_id,
                'title': chosen.title,
                'type': chosen.type,
                'current_location': chosen.current_location,
                'image_url': chosen.image_url,
                'similarity_score': round(chosen_score, 4),
            },
            'conn_type': conn_type,
            'conn_message': conn_message,
        })


# ── 퀵 액션 칩 API ─────────────────────────────────────────────────────────────

class ChatReasonView(APIView):
    """GET /api/chats/{chat_id}/reason/?artifact_id=1 — 왜 이거예요?"""

    @swagger_auto_schema(
        operation_description="GET /api/chats/{chat_id}/reason/ — 유물 추천 이유 조회",
        manual_parameters=[
            openapi.Parameter('artifact_id', openapi.IN_QUERY, required=True,
                              description="유물 cleveland_id", type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: openapi.Response('추천 이유', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'artifact_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'conn_type': openapi.Schema(type=openapi.TYPE_STRING),
                    'reason': openapi.Schema(type=openapi.TYPE_STRING),
                    'keywords': openapi.Schema(type=openapi.TYPE_ARRAY,
                                              items=openapi.Schema(type=openapi.TYPE_STRING)),
                },
            )),
            400: 'artifact_id 누락',
            404: '채팅 또는 유물 없음',
        },
    )
    def get(self, request, chat_id):
        chat, err = _get_chat_or_404(chat_id)
        if err:
            return err

        artifact_id = request.query_params.get('artifact_id')
        if not artifact_id:
            return Response({'error': 'artifact_id가 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        artifact = get_object_or_404(Artifact, cleveland_id=artifact_id)

        feedback_history = list(chat.feedback_history)
        history_count = len(chat.history)

        if artifact.embedding_vector and chat.history:
            viewed_artifacts = Artifact.objects.filter(id__in=chat.history, embedding_vector__isnull=False)
            history_vecs = [a.embedding_vector for a in viewed_artifacts]
            if history_vecs:
                query_vec = np.array(history_vecs, dtype=np.float32).mean(axis=0)
                query_norm = np.linalg.norm(query_vec)
                if query_norm > 0:
                    query_vec = query_vec / query_norm
                    vec = np.array(artifact.embedding_vector, dtype=np.float32)
                    norm = np.linalg.norm(vec)
                    similarity = float(np.dot(query_vec, vec / norm)) if norm > 0 else 0.0
                else:
                    similarity = 0.0
            else:
                similarity = 0.0
        else:
            similarity = 0.0

        conn_type = _decide_conn_type(similarity, feedback_history, history_count)

        # 유사도 상위 키워드 3개: technique, culture, type 순
        keywords = [v for v in [artifact.technique, artifact.culture, artifact.type] if v][:3]

        # reason: Groq LLM 생성, 실패 시 템플릿 fallback
        prompt = (
            f"추천 유물: {artifact.title}, {artifact.type}, {artifact.department}, {artifact.culture}\n"
            f"연결 방식: {conn_type}\n"
            f"유사도 상위 키워드: {', '.join(keywords)}\n\n"
            f"이 유물을 추천한 이유를 한국어로 2~3문장으로 설명해줘.\n"
            f"유물명은 영어 그대로 써도 돼.\n"
            f"반드시 한국어로만 출력해줘."
        )
        reason = _groq_generate(prompt) or CONN_MESSAGES[conn_type]

        return Response({
            'artifact_id': int(artifact_id),
            'conn_type': conn_type,
            'reason': reason,
            'keywords': keywords,
        })


class ChatSimilarView(APIView):
    """GET /api/chats/{chat_id}/similar/?artifact_id=1 — 비슷한 작품 더 보기"""

    @swagger_auto_schema(
        operation_description="GET /api/chats/{chat_id}/similar/ — 비슷한 유물 2~3개 조회",
        manual_parameters=[
            openapi.Parameter('artifact_id', openapi.IN_QUERY, required=True,
                              description="유물 cleveland_id", type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: openapi.Response('유사 유물 목록', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'artifact_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'similar_artifacts': openapi.Schema(type=openapi.TYPE_ARRAY,
                                                        items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                },
            )),
            400: 'artifact_id 누락 또는 임베딩 없음',
            404: '채팅 또는 유물 없음',
        },
    )
    def get(self, request, chat_id):
        chat, err = _get_chat_or_404(chat_id)
        if err:
            return err

        artifact_id = request.query_params.get('artifact_id')
        if not artifact_id:
            return Response({'error': 'artifact_id가 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        artifact = get_object_or_404(Artifact, cleveland_id=artifact_id)

        if not artifact.embedding_vector:
            return Response({'error': '해당 유물에 임베딩 벡터가 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        query_vec = np.array(artifact.embedding_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return Response({'error': '임베딩 벡터가 zero vector입니다.'}, status=status.HTTP_400_BAD_REQUEST)
        query_vec = query_vec / query_norm

        viewed_ids = set(chat.history) | {artifact.id}
        candidates = [
            a for a in Artifact.objects.filter(embedding_vector__isnull=False)
            if a.id not in viewed_ids
        ]

        scored = _cosine_scores(query_vec, candidates)

        similar_artifacts = [
            {
                'artifact_id': a.cleveland_id,
                'title': a.title,
                'type': a.type,
                'current_location': a.current_location,
                'image_url': a.image_url,
                'similarity_score': round(score, 4),
            }
            for score, a in scored[:3]
        ]

        return Response({'artifact_id': int(artifact_id), 'similar_artifacts': similar_artifacts})


class ChatShortestView(APIView):
    """GET /api/chats/{chat_id}/shortest/?artifact_id=1&current_location=102A — 짧은 경로로"""

    @swagger_auto_schema(
        operation_description="GET /api/chats/{chat_id}/shortest/ — 현재 위치에서 가장 가까운 유물 조회",
        manual_parameters=[
            openapi.Parameter('artifact_id', openapi.IN_QUERY, required=True,
                              description="기준 유물 cleveland_id", type=openapi.TYPE_INTEGER),
            openapi.Parameter('current_location', openapi.IN_QUERY, required=True,
                              description="현재 위치 (예: 102A)", type=openapi.TYPE_STRING),
        ],
        responses={
            200: openapi.Response('가장 가까운 유물', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'artifact_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'title': openapi.Schema(type=openapi.TYPE_STRING),
                    'type': openapi.Schema(type=openapi.TYPE_STRING),
                    'current_location': openapi.Schema(type=openapi.TYPE_STRING),
                    'image_url': openapi.Schema(type=openapi.TYPE_STRING),
                    'distance': openapi.Schema(type=openapi.TYPE_STRING),
                },
            )),
            400: '파라미터 누락',
            404: '채팅 없음 또는 후보 없음',
        },
    )
    def get(self, request, chat_id):
        chat, err = _get_chat_or_404(chat_id)
        if err:
            return err

        artifact_id = request.query_params.get('artifact_id')
        current_location = request.query_params.get('current_location', '')

        if not artifact_id:
            return Response({'error': 'artifact_id가 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)
        if not current_location:
            return Response({'error': 'current_location이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        current_gallery = _gallery_number(current_location)

        viewed_ids = set(chat.history) | {
            a.id for a in Artifact.objects.filter(cleveland_id=artifact_id)
        }
        candidates = list(Artifact.objects.exclude(id__in=viewed_ids).exclude(current_location=''))

        if not candidates:
            return Response({'error': '추천 가능한 유물이 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        def _distance(a):
            gallery = _gallery_number(a.current_location)
            if gallery < 0:
                return float('inf')
            return abs(gallery - current_gallery)

        candidates.sort(key=_distance)
        chosen = candidates[0]

        dist = _distance(chosen)
        if dist == 0:
            distance_label = "같은 갤러리"
        elif dist <= 5:
            distance_label = "근처 갤러리"
        else:
            distance_label = "다른 구역"

        return Response({
            'artifact_id': chosen.cleveland_id,
            'title': chosen.title,
            'type': chosen.type,
            'current_location': chosen.current_location,
            'image_url': chosen.image_url,
            'distance': distance_label,
        })


class ChatSummaryView(APIView):
    """GET /api/chats/{chat_id}/summary/ — 관람 요약"""

    @swagger_auto_schema(
        operation_description="GET /api/chats/{chat_id}/summary/ — 관람 요약 (통계 / 서사 / 후속 주제 / 스크립트)",
        responses={
            200: openapi.Response('관람 요약', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'chat_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'stats': openapi.Schema(type=openapi.TYPE_OBJECT),
                    'narrative': openapi.Schema(type=openapi.TYPE_STRING),
                    'next_themes': openapi.Schema(type=openapi.TYPE_ARRAY,
                                                  items=openapi.Schema(type=openapi.TYPE_STRING)),
                    'script': openapi.Schema(type=openapi.TYPE_ARRAY,
                                             items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                },
            )),
            404: '채팅 없음',
        },
    )
    def get(self, request, chat_id):
        chat, err = _get_chat_or_404(chat_id)
        if err:
            return err

        # ── 1. 방문 유물 목록 (순서 보존) ────────────────────────────────
        history_ids = list(chat.history)
        artifact_map = {
            a.id: a for a in Artifact.objects.filter(id__in=history_ids)
        }
        artifacts = [artifact_map[aid] for aid in history_ids if aid in artifact_map]

        # ── 2. 통계 ───────────────────────────────────────────────────────
        feedback_history = list(chat.feedback_history)
        liked = feedback_history.count(1)
        disliked = feedback_history.count(-1)

        stats = {
            'artifact_count': len(artifacts),
            'liked': liked,
            'disliked': disliked,
        }

        if not artifacts:
            return Response({
                'chat_id': chat_id,
                'stats': stats,
                'narrative': '아직 관람한 유물이 없어요.',
                'next_themes': [],
                'script': [],
            })

        # ── 3. 관람 서사 — 방문 유물의 keyword 시퀀스 기반 ───────────────
        keywords_seen = []
        for a in artifacts:
            if a.keyword and a.keyword not in keywords_seen:
                keywords_seen.append(a.keyword)

        # narrative: Groq LLM 생성, 실패 시 템플릿 fallback
        artifact_sequence = " → ".join(f"{a.title} ({a.type})" for a in artifacts)
        narrative_prompt = (
            f"관람한 유물 목록 (순서대로):\n{artifact_sequence}\n\n"
            f"이 관람 여정을 한국어로 1~2문장으로 서사적으로 요약해줘.\n"
            f"유물명은 영어 그대로 써도 돼.\n"
            f"반드시 한국어로만 출력해줘."
        )
        if len(keywords_seen) >= 2:
            fallback_narrative = f"{keywords_seen[0]}에서 시작해 {keywords_seen[-1]}으로 이어지는 여정이었어요."
        elif len(keywords_seen) == 1:
            fallback_narrative = f"{keywords_seen[0]} 중심으로 감상하신 여정이었어요."
        else:
            fallback_narrative = "다양한 유물을 감상하신 여정이었어요."

        narrative = _groq_generate(narrative_prompt) or fallback_narrative

        # ── 4. 후속 주제 추천 — 히스토리 평균 벡터 vs 미방문 키워드 ──────
        history_vecs = [
            a.embedding_vector for a in artifacts if a.embedding_vector
        ]
        next_themes = []
        if history_vecs:
            query_vec = np.array(history_vecs, dtype=np.float32).mean(axis=0)
            query_norm = np.linalg.norm(query_vec)

            if query_norm > 0:
                query_vec = query_vec / query_norm
                viewed_ids = set(history_ids)

                # 키워드별 대표 벡터(평균) 계산
                keyword_vecs: dict[str, list] = {}
                for a in Artifact.objects.filter(embedding_vector__isnull=False).exclude(id__in=viewed_ids).exclude(keyword=''):
                    keyword_vecs.setdefault(a.keyword, []).append(a.embedding_vector)

                keyword_scores = []
                for kw, vecs in keyword_vecs.items():
                    if kw in keywords_seen:
                        continue
                    avg = np.array(vecs, dtype=np.float32).mean(axis=0)
                    norm = np.linalg.norm(avg)
                    if norm == 0:
                        continue
                    score = float(np.dot(query_vec, avg / norm))
                    keyword_scores.append((score, kw))

                keyword_scores.sort(key=lambda x: x[0], reverse=True)
                next_themes = [kw for _, kw in keyword_scores[:2]]

        # ── 5. 스크립트 — 유물 순서대로 conn_type 재구성 ─────────────────
        script = []
        for i, artifact in enumerate(artifacts):
            if i == 0:
                conn_type = "story"
            else:
                # 이전까지 히스토리 평균 벡터로 conn_type 결정
                prev_vecs = [
                    a.embedding_vector for a in artifacts[:i] if a.embedding_vector
                ]
                if prev_vecs and artifact.embedding_vector:
                    pv = np.array(prev_vecs, dtype=np.float32).mean(axis=0)
                    pv_norm = np.linalg.norm(pv)
                    if pv_norm > 0:
                        pv = pv / pv_norm
                        av = np.array(artifact.embedding_vector, dtype=np.float32)
                        av_norm = np.linalg.norm(av)
                        sim = float(np.dot(pv, av / av_norm)) if av_norm > 0 else 0.0
                    else:
                        sim = 0.0
                    partial_feedback = feedback_history[:i]
                    conn_type = _decide_conn_type(sim, partial_feedback, i)
                else:
                    conn_type = "story"

            script.append({
                'artifact_id': artifact.cleveland_id,
                'title': artifact.title,
                'conn_message': CONN_MESSAGES[conn_type],
            })

        return Response({
            'chat_id': chat_id,
            'stats': stats,
            'narrative': narrative,
            'next_themes': next_themes,
            'script': script,
        })


class ChatRouteView(APIView):
    """GET /api/chats/{chat_id}/route/?current_location=102A&artifact_id=1 — 경로 안내"""

    @swagger_auto_schema(
        operation_description="GET /api/chats/{chat_id}/route/ — 현재 위치에서 목적지 유물까지 경로 안내",
        manual_parameters=[
            openapi.Parameter('current_location', openapi.IN_QUERY, required=True,
                              description="현재 위치 (예: 102A)", type=openapi.TYPE_STRING),
            openapi.Parameter('artifact_id', openapi.IN_QUERY, required=True,
                              description="목적지 유물 cleveland_id", type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: openapi.Response('경로 안내', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'destination': openapi.Schema(type=openapi.TYPE_OBJECT),
                    'waypoints': openapi.Schema(type=openapi.TYPE_ARRAY,
                                                items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                    'estimated_distance': openapi.Schema(type=openapi.TYPE_STRING),
                },
            )),
            400: '파라미터 누락',
            404: '채팅 또는 유물 없음',
        },
    )
    def get(self, request, chat_id):
        chat, err = _get_chat_or_404(chat_id)
        if err:
            return err

        current_location = request.query_params.get('current_location', '')
        artifact_id = request.query_params.get('artifact_id')

        if not current_location:
            return Response({'error': 'current_location이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)
        if not artifact_id:
            return Response({'error': 'artifact_id가 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        destination = get_object_or_404(Artifact, cleveland_id=artifact_id)

        # ── 거리 계산 ─────────────────────────────────────────────────────
        # TODO: 팀원 최적화 모델 연동 — 현재는 갤러리 번호 앞 숫자 차이로 임시 계산
        src_gallery = _gallery_number(current_location)
        dst_gallery = _gallery_number(destination.current_location)
        raw_distance = abs(dst_gallery - src_gallery) if src_gallery >= 0 and dst_gallery >= 0 else 0

        if raw_distance == 0:
            estimated_distance = "같은 갤러리"
        elif raw_distance < 20:
            estimated_distance = "가까운 거리"
        elif raw_distance < 50:
            estimated_distance = "중간 거리"
        else:
            estimated_distance = "먼 거리"

        # ── 경유 유물 생성 (거리 임계값 50 이상) ─────────────────────────
        waypoints = []

        if raw_distance >= 50:
            # 히스토리 평균 벡터 계산
            history_ids = list(chat.history)
            viewed_artifacts = Artifact.objects.filter(id__in=history_ids, embedding_vector__isnull=False)
            history_vecs = [a.embedding_vector for a in viewed_artifacts]

            if history_vecs:
                query_vec = np.array(history_vecs, dtype=np.float32).mean(axis=0)
                query_norm = np.linalg.norm(query_vec)

                if query_norm > 0:
                    query_vec = query_vec / query_norm

                    # TODO: 팀원 최적화 모델 연동 — 경로상 갤러리 범위 필터도 최적화 모델로 교체 예정
                    lo_gallery = min(src_gallery, dst_gallery)
                    hi_gallery = max(src_gallery, dst_gallery)

                    viewed_ids = set(history_ids) | {destination.id}
                    # 경로 사이 갤러리 번호에 있는 유물 필터
                    between = [
                        a for a in Artifact.objects.filter(embedding_vector__isnull=False).exclude(id__in=viewed_ids)
                        if lo_gallery < _gallery_number(a.current_location) < hi_gallery
                    ]

                    scored = _cosine_scores(query_vec, between)

                    for score, artifact in scored[:2]:
                        waypoints.append({
                            'artifact_id': artifact.cleveland_id,
                            'title': artifact.title,
                            'current_location': artifact.current_location,
                            'image_url': artifact.image_url,
                            'conn_type': 'shock',
                            'conn_message': CONN_MESSAGES['shock'],
                        })

        return Response({
            'destination': {
                'artifact_id': destination.cleveland_id,
                'title': destination.title,
                'current_location': destination.current_location,
                'image_url': destination.image_url,
            },
            'waypoints': waypoints,
            'estimated_distance': estimated_distance,
        })


class ChatHistoryView(APIView):
    """GET /api/chats/{chat_id}/history/ — 관람 타임라인"""

    @swagger_auto_schema(
        operation_description="GET /api/chats/{chat_id}/history/ — 방문 유물 목록 순서대로 반환",
        responses={
            200: openapi.Response('관람 타임라인', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'chat_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'artifacts': openapi.Schema(type=openapi.TYPE_ARRAY,
                                                items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                },
            )),
            404: '채팅 없음',
        },
    )
    def get(self, request, chat_id):
        chat, err = _get_chat_or_404(chat_id)
        if err:
            return err

        history_ids = list(chat.history)
        artifact_map = {
            a.id: a for a in Artifact.objects.filter(id__in=history_ids)
        }

        artifacts = [
            {
                'artifact_id': artifact_map[aid].cleveland_id,
                'title': artifact_map[aid].title,
                'type': artifact_map[aid].type,
                'current_location': artifact_map[aid].current_location,
                'image_url': artifact_map[aid].image_url,
            }
            for aid in history_ids if aid in artifact_map
        ]

        return Response({'chat_id': chat_id, 'artifacts': artifacts})


class ChatShareView(APIView):
    """POST /api/chats/{chat_id}/share/ — 여정 공유 URL 생성"""

    @swagger_auto_schema(
        operation_description="POST /api/chats/{chat_id}/share/ — 고유 공유 URL 생성 (이미 있으면 기존 URL 반환)",
        responses={
            200: openapi.Response('공유 URL', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'chat_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'share_url': openapi.Schema(type=openapi.TYPE_STRING),
                },
            )),
            404: '채팅 없음',
        },
    )
    def post(self, request, chat_id):
        import uuid
        chat, err = _get_chat_or_404(chat_id)
        if err:
            return err

        if not chat.share_token:
            chat.share_token = uuid.uuid4()
            chat.save(update_fields=['share_token'])

        base_url = request.build_absolute_uri('/').rstrip('/')
        share_url = f"{base_url}/shared/{chat.share_token}/"

        return Response({'chat_id': chat_id, 'share_url': share_url})
