from django.core.management.base import BaseCommand
from sentence_transformers import SentenceTransformer
from artifacts.models import Artifact


class Command(BaseCommand):
    help = "embedding_vector가 없는 유물에 paraphrase-multilingual-MiniLM-L12-v2 벡터 생성"

    def add_arguments(self, parser):
        parser.add_argument("--batch", type=int, default=500)

    def handle(self, *args, **options):
        batch_size = options["batch"]

        qs = Artifact.objects.filter(embedding_vector__isnull=True).exclude(embedding_text="")
        total = qs.count()
        if total == 0:
            self.stdout.write("임베딩 생성 대상 없음.")
            return

        self.stdout.write(f"임베딩 생성 대상: {total}개 — 모델 로딩 중...")
        model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

        processed = 0
        offset = 0

        while offset < total:
            batch = list(qs[offset: offset + batch_size])
            if not batch:
                break

            texts = [a.embedding_text for a in batch]
            vectors = model.encode(texts, batch_size=64, show_progress_bar=False)

            for artifact, vector in zip(batch, vectors):
                artifact.embedding_vector = vector.tolist()

            Artifact.objects.bulk_update(batch, ["embedding_vector"])

            processed += len(batch)
            self.stdout.write(f"진행 중... {processed}/{total}")
            offset += batch_size

        self.stdout.write(self.style.SUCCESS(f"완료! {processed}개 임베딩 생성"))
