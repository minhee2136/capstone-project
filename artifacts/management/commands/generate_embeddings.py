from django.core.management.base import BaseCommand
from artifacts.models import Artifact
from sentence_transformers import SentenceTransformer

class Command(BaseCommand):
    help = "DB에 저장된 유물의 임베딩 벡터 생성"

    def handle(self, *args, **options):
        model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        
        BATCH_SIZE = 64

        artifacts = list(Artifact.objects.filter(embedding_vector__isnull=True).exclude(embedding_text=""))
        total = len(artifacts)
        self.stdout.write(f"임베딩 생성 대상: {total}개")

        for i in range(0, total, BATCH_SIZE):
            batch = artifacts[i:i + BATCH_SIZE]
            texts = [a.embedding_text for a in batch]
            vectors = model.encode(texts, batch_size=BATCH_SIZE, show_progress_bar=False)

            for artifact, vector in zip(batch, vectors):
                artifact.embedding_vector = vector.tolist()
            Artifact.objects.bulk_update(batch, ["embedding_vector"])

            self.stdout.write(f"진행중... {min(i + BATCH_SIZE, total)}/{total}")

        self.stdout.write(self.style.SUCCESS(f"완료! {total}개 임베딩 생성"))