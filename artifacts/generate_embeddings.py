from django.core.management.base import BaseCommand
from artifacts.models import Artifact
from sentence_transformers import SentenceTransformer


class Command(BaseCommand):
    help = "DB에 저장된 유물의 임베딩 벡터 생성"

    def handle(self, *args, **options):
        model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

        artifacts = Artifact.objects.filter(embedding_vector__isnull=True)
        total = artifacts.count()
        self.stdout.write(f"임베딩 생성 대상: {total}개")
        

        for i, artifact in enumerate(artifacts):
            if not artifact.embedding_text:
                continue

            vector = model.encode(artifact.embedding_text).tolist()
            artifact.embedding_vector = vector
            artifact.save(update_fields=["embedding_vector"])

            if (i + 1) % 100 == 0:
                self.stdout.write(f"진행중... {i+1}/{total}")

        self.stdout.write(self.style.SUCCESS(f"완료! {total}개 임베딩 생성"))