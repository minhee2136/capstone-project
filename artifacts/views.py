import numpy as np
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.conf import settings

from .models import Artifact
from .serializers import ArtifactDetailSerializer

from groq import Groq
client = Groq(api_key=settings.GROQ_API_KEY)


class SyncArtifactsView(APIView):

    @swagger_auto_schema(
        operation_summary="유물 DB 생성",
    )
    def post(self, request):
        from artifacts.tasks import sync_artifacts_task
        sync_artifacts_task()
        return Response({'message': '동기화 작업이 시작되었습니다.'}, status=status.HTTP_202_ACCEPTED)


class ArtifactDetailView(generics.RetrieveAPIView):
    serializer_class = ArtifactDetailSerializer
    lookup_field = 'cleveland_id'
    lookup_url_kwarg = 'artifact_id'

    def get_queryset(self):
        return Artifact.objects.all()

    @swagger_auto_schema(
        operation_summary="유물 상세 정보 조회",
    )
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)


class ArtifactRecentView(APIView):

    @swagger_auto_schema(
        operation_summary="이전 유물 요약"
            
    )
    def get(self, request, artifact_id):
        from chat.models import Message
        from sessions.models import Session

        session_id = request.query_params.get('session_id')
        if not session_id:
            return Response({'error': 'session_id가 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return Response({'error': '세션을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        messages = Message.objects.filter(
            session=session,
            role=Message.Role.ASSISTANT,
            artifact_id__isnull=False,
        ).exclude(artifact_id=artifact_id).order_by('-created_at')

        seen = set()
        recent = []
        for msg in messages:
            if msg.artifact_id not in seen:
                seen.add(msg.artifact_id)
                try:
                    artifact = Artifact.objects.get(cleveland_id=msg.artifact_id)
                except Artifact.DoesNotExist:
                    continue
                recent.append({
                    'artifact_id': artifact.cleveland_id,
                    'title': artifact.title,
                    'image_url': artifact.image_url,
                })
            if len(recent) == 3:
                break

        return Response({'recent': recent})


