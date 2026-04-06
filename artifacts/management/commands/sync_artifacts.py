import re
import requests
from django.core.management.base import BaseCommand
from artifacts.models import Artifact

CMA_API_URL = "https://openaccess-api.clevelandart.org/api/artworks/"


def clean_html(text):
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text).strip()


def apply_fields(artifact, api_data):
    images = api_data.get('images') or {}
    web = images.get('web') or {}

    def s(val, default=''):
        return val if val is not None else default

    artifact.accession_number = s(api_data.get('accession_number'))
    artifact.share_license_status = s(api_data.get('share_license_status'))
    artifact.is_active = (api_data.get('share_license_status') == 'CC0')
    artifact.title = s(api_data.get('title'))
    artifact.tombstone = clean_html(s(api_data.get('tombstone')))
    artifact.creation_date = s(api_data.get('creation_date'))
    artifact.creation_date_earliest = api_data.get('creation_date_earliest')
    artifact.creation_date_latest = api_data.get('creation_date_latest')
    artifact.culture = api_data.get('culture') or []
    artifact.technique = s(api_data.get('technique'))
    artifact.department = s(api_data.get('department'))
    artifact.collection = s(api_data.get('collection'))
    artifact.type = s(api_data.get('type'))
    artifact.current_location = s(api_data.get('current_location'))
    artifact.measurements = s(api_data.get('measurements'))
    artifact.description = clean_html(s(api_data.get('description')))
    artifact.did_you_know = clean_html(s(api_data.get('did_you_know')))
    artifact.image_url = s(web.get('url'))
    artifact.updated_at = s(api_data.get('updated_at'))
    artifact.embedding_text = ' '.join(filter(None, [
        artifact.title,
        ', '.join(artifact.culture) if isinstance(artifact.culture, list) else str(artifact.culture),
        artifact.technique,
        artifact.department,
        artifact.description,
    ]))


class Command(BaseCommand):
    help = "CMA API와 DB를 동기화하고 임베딩을 생성합니다"

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='최대 수집 건수 (0=전체)')
        parser.add_argument('--batch', type=int, default=100)
        parser.add_argument('--skip-embedding', action='store_true', help='임베딩 생성 건너뜀')

    def handle(self, *args, **options):
        batch_size = options['batch']
        max_limit = options['limit']
        skip_embedding = options['skip_embedding']

        skip = 0
        created_count = 0
        updated_count = 0
        skipped_count = 0
        embedding_targets = []

        self.stdout.write("=== CMA API 동기화 시작 ===")

        while True:
            if max_limit and skip >= max_limit:
                break

            current_batch = batch_size if not max_limit else min(batch_size, max_limit - skip)
            params = {"limit": current_batch, "skip": skip, "cc0": 1}

            self.stdout.write(f"API 호출 중... skip={skip}, batch={current_batch}")

            try:
                response = requests.get(CMA_API_URL, params=params, timeout=30)
                response.raise_for_status()
            except requests.RequestException as e:
                self.stderr.write(f"API 오류: {e}")
                break

            artworks = response.json().get("data", [])
            if not artworks:
                self.stdout.write("더 이상 데이터 없음. 종료.")
                break

            for aw in artworks:
                cleveland_id = aw["id"]
                api_updated_at = aw.get("updated_at", "")
                api_license = aw.get("share_license_status", "")

                try:
                    artifact = Artifact.objects.get(cleveland_id=cleveland_id)
                    # 기존에 CC0였다가 상태 바뀐 경우
                    if artifact.is_active and api_license != 'CC0':
                        artifact.is_active = False
                        artifact.share_license_status = api_license
                        artifact.save(update_fields=['is_active', 'share_license_status'])
                        updated_count += 1
                        continue

                    # updated_at 동일하면 스킵
                    if artifact.updated_at == api_updated_at:
                        skipped_count += 1
                        continue

                    # updated_at 다르면 업데이트
                    apply_fields(artifact, aw)
                    artifact.embedding_vector = None  # 재생성 대상으로 초기화
                    artifact.save()
                    updated_count += 1
                    if artifact.is_active:
                        embedding_targets.append(artifact.id)

                except Artifact.DoesNotExist:
                    artifact = Artifact(cleveland_id=cleveland_id)
                    apply_fields(artifact, aw)
                    artifact.save()
                    created_count += 1
                    if artifact.is_active:
                        embedding_targets.append(artifact.id)

            self.stdout.write(
                f"배치 완료 — 신규: {created_count}, 업데이트: {updated_count}, 스킵: {skipped_count}"
            )
            skip += current_batch

        self.stdout.write(self.style.SUCCESS(
            f"\n동기화 완료! 신규: {created_count}개, 업데이트: {updated_count}개, 스킵: {skipped_count}개"
        ))

        if skip_embedding or not embedding_targets:
            if not embedding_targets:
                self.stdout.write("임베딩 생성 대상 없음.")
            return

        # 임베딩 생성
        self.stdout.write(f"\n=== 임베딩 생성 시작: {len(embedding_targets)}개 ===")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            self.stderr.write("sentence-transformers 미설치. 임베딩 생성 건너뜀.")
            return

        model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        artifacts = Artifact.objects.filter(id__in=embedding_targets, is_active=True)

        for i, artifact in enumerate(artifacts):
            if not artifact.embedding_text:
                continue
            artifact.embedding_vector = model.encode(artifact.embedding_text).tolist()
            artifact.save(update_fields=["embedding_vector"])
            if (i + 1) % 50 == 0:
                self.stdout.write(f"임베딩 진행중... {i+1}/{len(embedding_targets)}")

        self.stdout.write(self.style.SUCCESS(f"임베딩 완료! {len(embedding_targets)}개 생성"))
