from django.core.management.base import BaseCommand
from artifacts.models import Artifact

KEYWORD_TYPE_MAP = {
    "회화": ["Painting"],
    "조각·공예": ["Sculpture", "Metalwork", "Ceramic", "Silver", "Glass"],
    "전쟁·무기": ["Arms and Armor"],
    "역사·기록": ["Bound Volume", "Manuscript"],
}

KEYWORD_DEPT_MAP = {
    "동양 문화": ["Chinese Art", "Japanese Art", "Korean Art", "Indian and Southeast Asian Art"],
    "신화·종교": ["Egyptian and Ancient Near Eastern Art", "Greek and Roman Art", "Islamic Art"],
}

# type 기준 역인덱스
TYPE_TO_KEYWORD = {t: kw for kw, types in KEYWORD_TYPE_MAP.items() for t in types}
DEPT_TO_KEYWORD = {d: kw for kw, depts in KEYWORD_DEPT_MAP.items() for d in depts}


def resolve_keyword(art_type: str, department: str) -> str:
    return TYPE_TO_KEYWORD.get(art_type) or DEPT_TO_KEYWORD.get(department) or ""


class Command(BaseCommand):
    help = "DB 유물의 type/department 기준으로 keyword 필드 태깅"

    def add_arguments(self, parser):
        parser.add_argument("--batch", type=int, default=1000)
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="이미 keyword가 있는 유물도 덮어씀 (기본: keyword가 빈 것만 처리)",
        )

    def handle(self, *args, **options):
        batch_size = options["batch"]
        overwrite = options["overwrite"]

        qs = Artifact.objects.all() if overwrite else Artifact.objects.filter(keyword="")
        id_list = list(qs.values_list("id", flat=True))
        total = len(id_list)

        if total == 0:
            self.stdout.write("태깅 대상 없음.")
            return

        self.stdout.write(f"키워드 태깅 대상: {total}개")

        processed = 0
        tagged = 0
        offset = 0

        while offset < total:
            batch_ids = id_list[offset: offset + batch_size]
            batch = list(Artifact.objects.filter(id__in=batch_ids).values("id", "type", "department"))
            if not batch:
                break

            updates = []
            for row in batch:
                kw = resolve_keyword(row["type"], row["department"])
                updates.append(Artifact(id=row["id"], keyword=kw))
                if kw:
                    tagged += 1

            Artifact.objects.bulk_update(updates, ["keyword"])
            processed += len(batch)
            self.stdout.write(f"진행 중... {processed}/{total}")
            offset += batch_size

        self.stdout.write(self.style.SUCCESS(
            f"완료! {processed}개 처리, {tagged}개 키워드 매핑됨"
        ))
