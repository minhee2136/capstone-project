import numpy as np
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.conf import settings

from .models import Artifact
from .serializers import ArtifactDetailSerializer

from groq import Groq
client = Groq(api_key=settings.GROQ_API_KEY)


class SyncArtifactsView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/artifacts/sync/ — Celery task로 유물 동기화 작업 큐에 등록",
        responses={202: '동기화 작업 시작됨'},
    )
    def post(self, request):
        from artifacts.tasks import sync_artifacts_task
        sync_artifacts_task.delay()
        return Response({'message': '동기화 작업이 시작되었습니다.'}, status=status.HTTP_202_ACCEPTED)


class ArtifactDetailView(generics.RetrieveAPIView):
    serializer_class = ArtifactDetailSerializer
    lookup_field = 'cleveland_id'
    lookup_url_kwarg = 'artifact_id'

    def get_queryset(self):
        return Artifact.objects.all()

    @swagger_auto_schema(
        operation_description="GET /api/artifacts/{artifact_id}/ — 유물 상세 정보 조회",
        responses={
            200: openapi.Response('유물 상세 조회 성공', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'artifact_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'title': openapi.Schema(type=openapi.TYPE_STRING),
                    'type': openapi.Schema(type=openapi.TYPE_STRING),
                    'department': openapi.Schema(type=openapi.TYPE_STRING),
                    'collection': openapi.Schema(type=openapi.TYPE_STRING),
                    'technique': openapi.Schema(type=openapi.TYPE_STRING),
                    'culture': openapi.Schema(type=openapi.TYPE_STRING),
                    'creation_date_earliest': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'creation_date_latest': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'current_location': openapi.Schema(type=openapi.TYPE_STRING),
                    'image_url': openapi.Schema(type=openapi.TYPE_STRING),
                    'description': openapi.Schema(type=openapi.TYPE_STRING),
                    'did_you_know': openapi.Schema(type=openapi.TYPE_STRING),
                },
            )),
            404: '유물 없음',
        },
    )
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)


class ArtifactRelatedView(APIView):

    @swagger_auto_schema(
        operation_description="GET /api/artifacts/{artifact_id}/related/ — 같은 department 또는 culture의 유사 유물 Top 5",
        responses={200: "연관 유물 조회 성공"},
    )
    def get(self, request, artifact_id):
        import numpy as np
        artifact = get_object_or_404(Artifact, cleveland_id=artifact_id)
        artifact_vector = artifact.get_embedding_vector()

        if artifact_vector is None:
            return Response({'artifact_id': artifact_id, 'related': []})

        candidates = Artifact.objects.filter(
            is_active=True,
            embedding_vector__isnull=False,
        ).exclude(cleveland_id=artifact_id)

        # 같은 department 또는 culture 필터
        dept_filter = candidates.filter(department=artifact.department) if artifact.department else candidates.none()
        culture_filter = candidates.filter(culture__overlap=artifact.culture) if artifact.culture else candidates.none()
        candidates = (dept_filter | culture_filter).distinct()

        norm_a = np.linalg.norm(artifact_vector)
        if norm_a == 0:
            return Response({'artifact_id': artifact_id, 'related': []})

        scores = []
        for candidate in candidates:
            vec = candidate.get_embedding_vector()
            if vec is None:
                continue
            norm_b = np.linalg.norm(vec)
            if norm_b == 0:
                continue
            score = float(np.dot(artifact_vector, vec) / (norm_a * norm_b))
            scores.append((score, candidate))

        scores.sort(key=lambda x: x[0], reverse=True)

        related = [
            {
                'artifact_id': c.cleveland_id,
                'title': c.title,
                'department': c.department,
                'culture': c.culture,
                'image_url': c.image_url,
                'current_location': c.current_location,
                'similarity_score': round(score, 4),
            }
            for score, c in scores[:5]
        ]

        return Response({'artifact_id': artifact_id, 'related': related})
