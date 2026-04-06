import re
import requests
from django.core.management.base import BaseCommand
from artifacts.models import Artifact

CMA_API_URL = "https://openaccess-api.clevelandart.org/api/artworks/"


def clean_html(text):
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text).strip()


class Command(BaseCommand):
    help = "Cleveland Museum API에서 유물 데이터를 가져와 DB에 저장"

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=6243)
        parser.add_argument('--department', type=str, default=None)
        parser.add_argument('--batch', type=int, default=100)

    def handle(self, *args, **options):
        total_limit = options['limit']
        department = options['department']
        batch_size = options['batch']

        skip = 0
        total_created = 0
        total_updated = 0

        while skip < total_limit:
            current_batch = min(batch_size, total_limit - skip)

            params = {
                "limit": current_batch,
                "skip": skip,
                "has_image": 1,
                "cc0": 1,
                "currently_on_view": 1,
            }
            if department:
                params["department"] = department

            self.stdout.write(f"API 호출 중... skip={skip}, batch={current_batch}")

            response = requests.get(CMA_API_URL, params=params)
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
                images = aw.get("images", {})
                image_url = ""
                if images:
                    web = images.get("web", {})
                    image_url = web.get("url", "") if web else ""

                embedding_text = " ".join(filter(None, [
                    aw.get("title", ""),
                    aw.get("type", ""),
                    aw.get("technique", ""),
                    aw.get("department", ""),
                    aw.get("collection", ""),
                    str(aw.get("creation_date_earliest", "") or ""),
                    str(aw.get("creation_date_latest", "") or ""),
                    aw.get("current_location", "") or "",
                    clean_html(aw.get("description", "")),
                    clean_html(aw.get("did_you_know", "")),
                    ", ".join(aw.get("culture", [])),
                ]))

                obj, created = Artifact.objects.update_or_create(
                    cleveland_id=aw["id"],
                    defaults={
                        "title": aw.get("title", ""),
                        "type": aw.get("type", ""),
                        "department": aw.get("department", ""),
                        "collection": aw.get("collection", ""),
                        "technique": aw.get("technique", ""),
                        "culture": aw.get("culture", []),
                        "creation_date_earliest": aw.get("creation_date_earliest"),
                        "creation_date_latest": aw.get("creation_date_latest"),
                        "current_location": aw.get("current_location", "") or "",
                        "image_url": image_url,
                        "description": clean_html(aw.get("description", "")),
                        "did_you_know": clean_html(aw.get("did_you_know", "")),
                        "embedding_text": embedding_text,
                        "embedding_vector": None,
                    }
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
            skip += current_batch

        self.stdout.write(self.style.SUCCESS(
            f"\n전체 완료! 신규: {total_created}개, 업데이트: {total_updated}개"
        ))