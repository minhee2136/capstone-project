import numpy as np
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from openai import OpenAI
from django.conf import settings

from sessions.models import Session
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


class ArtifactDetailView(APIView):

    @swagger_auto_schema(
        operation_description="GET /api/artifacts/{artifact_id}/?session_id=xxx — 유물 상세 정보 조회 (session_id 전달 시 맞춤 설명 포함)",
        manual_parameters=[
            openapi.Parameter('session_id', openapi.IN_QUERY, description="세션 ID (선택)", type=openapi.TYPE_INTEGER),
        ],
        responses={200: "유물 상세 조회 성공"},
    )
    def get(self, request, artifact_id):
        artifact = get_object_or_404(Artifact, cleveland_id=artifact_id)
        data = ArtifactDetailSerializer(artifact).data

        session_id = request.query_params.get('session_id')
        if session_id:
            try:
                session = Session.objects.get(id=session_id)
            except Session.DoesNotExist:
                return Response({'error': '세션을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

            knowledge_level = session.knowledge_level or 'intermediate'
            level_guide = {'beginner': '쉬운 말로', 'intermediate': '일반적으로', 'advanced': '학술적으로'}
            prompt = (
                f"다음 유물에 대해 {knowledge_level} 수준의 관람객에게 맞는 설명을 3-4문장으로 작성해줘.\n"
                f"- 제목: {artifact.title}\n"
                f"- 문화권: {artifact.culture}\n"
                f"- 기법: {artifact.technique}\n"
                f"- 부서: {artifact.department}\n"
                f"- 기본 설명: {artifact.description}\n"
                f"- 흥미로운 사실: {artifact.did_you_know}\n"
                f"한국어로 답해줘. {level_guide.get(knowledge_level, '일반적으로')} 설명해줘."
            )
            try:
                gpt_response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                )
                data['custom_description'] = gpt_response.choices[0].message.content
                data['knowledge_level'] = knowledge_level
            except Exception as e:
                return Response({'error': f'GPT 호출 실패: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(data)


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
