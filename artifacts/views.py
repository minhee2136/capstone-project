from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from openai import OpenAI
from django.conf import settings

from sessions.models import Session
from .models import Artifact
from .serializers import ArtifactDetailSerializer, ArtifactDescriptionSerializer

client = OpenAI(api_key=settings.OPENAI_API_KEY)


class ArtifactDetailView(APIView):

    @swagger_auto_schema(
        operation_description="GET /api/artifacts/{artifact_id}/ — 유물 상세 정보 조회",
        responses={200: "유물 상세 조회 성공"},
    )
    def get(self, request, artifact_id):
        artifact = get_object_or_404(Artifact, id=artifact_id)
        serializer = ArtifactDetailSerializer(artifact)
        return Response(serializer.data)


class ArtifactDescriptionView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/artifacts/{artifact_id}/description/ — 맞춤 설명 + 연결 유물 생성",
        request_body=ArtifactDescriptionSerializer,
        responses={200: "맞춤 설명 생성 성공"},
    )
    def post(self, request, artifact_id):
        artifact = get_object_or_404(Artifact, id=artifact_id)
        serializer = ArtifactDescriptionSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        session = get_object_or_404(Session, id=serializer.validated_data['session_id'])

        # 히스토리 기반 연결 유물 조회
        from chat.models import Message
        history_messages = Message.objects.filter(
            session=session,
            role='assistant',
            artifact_id__isnull=False,
        ).exclude(artifact_id=artifact_id).values_list('artifact_id', flat=True)

        history_artifacts = Artifact.objects.filter(id__in=history_messages)
        history_text = ', '.join([a.title for a in history_artifacts]) if history_artifacts else '없음'

        # GPT-4o-mini로 맞춤 설명 + 연결성 생성
        gpt_response = client.chat.completions.create(
            model=settings.GPT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"당신은 뮤지엄 큐레이터입니다. "
                        f"사용자 관심사: {session.interest_tags}, "
                        f"지식 수준: {session.knowledge_level}. "
                        f"이전에 관람한 유물: {history_text}. "
                        f"아래 유물에 대해 사용자 맞춤 설명과 이전 유물과의 연결성을 설명해주세요."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"유물명: {artifact.title}\n"
                        f"설명: {artifact.description}\n"
                        f"제작 시기: {artifact.creation_date_earliest}~{artifact.creation_date_latest}\n"
                        f"문화권: {artifact.culture}"
                    )
                }
            ],
        )
        gpt_content = gpt_response.choices[0].message.content

        # 연결 유물 추천 (코사인 유사도 기반 상위 3개)
        import numpy as np
        artifact_vector = artifact.get_embedding_vector()
        related = []

        if artifact_vector is not None:
            candidates = Artifact.objects.exclude(id=artifact_id).exclude(
                embedding_vector__isnull=True
            )
            scores = []
            for candidate in candidates:
                vec = candidate.get_embedding_vector()
                if vec is not None:
                    score = float(np.dot(artifact_vector, vec) / (
                        np.linalg.norm(artifact_vector) * np.linalg.norm(vec) + 1e-10
                    ))
                    scores.append((score, candidate))
            scores.sort(key=lambda x: x[0], reverse=True)
            related = [
                {
                    'artifact_id': c.id,
                    'title': c.title,
                    'image_url': c.image_url,
                    'location': c.current_location,
                    'reason': '',
                }
                for _, c in scores[:3]
            ]

        return Response({
            'artifact_id': artifact.id,
            'description': gpt_content,
            'connection': history_text,
            'related': related,
        })