import re
import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from artifacts.models import Artifact

CMA_API_URL = "https://openaccess-api.clevelandart.org/api/artworks/"


def clean_html(text):
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text).strip()


def build_embedding_text(aw: dict, culture_str: str) -> str:
    parts = [
        aw.get("title", ""),
        aw.get("type", ""),
        aw.get("department", ""),
        aw.get("collection", ""),
        aw.get("technique", ""),
        culture_str,
        str(aw.get("creation_date_earliest", "") or ""),
        str(aw.get("creation_date_latest", "") or ""),
        aw.get("current_location", "") or "",
        clean_html(aw.get("description", ""))[:300],
    ]
    return " | ".join(p for p in parts if p)


class Command(BaseCommand):
    help = "CMA API에서 유물 데이터를 수집해 DB에 저장 (임베딩·키워드 제외)"

    def add_arguments(self, parser):
        parser.add_argument("--batch", type=int, default=100)

    def handle(self, *args, **options):
        batch_size = options["batch"]
        skip = 0
        total_created = 0
        total_updated = 0

        # 수집 시작 전 전체 is_active=False로 초기화
        # 수집 완료 후 False로 남은 유물 = 더 이상 전시 중이 아닌 것 → 삭제
        self.stdout.write("기존 유물 is_active 초기화 중...")
        Artifact.objects.all().update(is_active=False)

        while True:
            params = {
                "limit": batch_size,
                "skip": skip,
                "has_image": 1,
                "cc0": 1,
                "currently_on_view": 1,
            }

            self.stdout.write(f"API 호출 중... skip={skip}, batch={batch_size}")
            response = requests.get(CMA_API_URL, params=params, timeout=30)

            if response.status_code != 200:
                self.stderr.write(f"API 오류: {response.status_code}")
                break

            data = response.json()
            artworks = data.get("data", [])

            if not artworks:
                self.stdout.write("더 이상 데이터 없음. 종료.")
                break

            created_count = 0
            updated_count = 0

            for aw in artworks:
                # current_location이 비어있으면 실제 전시 중이 아닌 유물 → 건너뜀
                # (CMA API 응답에 currently_on_view 필드 없음, current_location으로 판별)
                if not (aw.get("current_location") or "").strip():
                    continue

                images = aw.get("images") or {}
                web = images.get("web") or {}
                image_url = web.get("url", "")

                culture_raw = aw.get("culture", [])
                culture_str = culture_raw[0] if culture_raw else ""

                description = clean_html(aw.get("description", ""))
                embedding_text = build_embedding_text(aw, culture_str)

                _, created = Artifact.objects.update_or_create(
                    cleveland_id=aw["id"],
                    defaults={
                        "title": aw.get("title", ""),
                        "type": aw.get("type", ""),
                        "department": aw.get("department", ""),
                        "collection": aw.get("collection", ""),
                        "technique": aw.get("technique", ""),
                        "culture": culture_str,
                        "creation_date_earliest": aw.get("creation_date_earliest"),
                        "creation_date_latest": aw.get("creation_date_latest"),
                        "current_location": aw.get("current_location", "") or "",
                        "image_url": image_url,
                        "description": description,
                        "embedding_text": embedding_text,
                        "embedding_vector": None,
                        "is_active": True,
                        "updated_at": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

            total_created += created_count
            total_updated += updated_count
            self.stdout.write(
                f"배치 완료 — 신규: {created_count}, 업데이트: {updated_count} "
                f"/ 누적: {total_created + total_updated}개"
            )
            skip += batch_size

        # is_active=False로 남은 유물 삭제 (현재 전시 중이 아닌 유물)
        deleted_qs = Artifact.objects.filter(is_active=False)
        deleted_count = deleted_qs.count()
        deleted_qs.delete()
        self.stdout.write(f"전시 종료 유물 삭제: {deleted_count}개")

        self.stdout.write(self.style.SUCCESS(
            f"\n수집 완료! 신규: {total_created}개, 업데이트: {total_updated}개, 삭제: {deleted_count}개"
        ))
