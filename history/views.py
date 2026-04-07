import numpy as np
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from sessions.models import Session
from artifacts.models import Artifact
from .models import ViewHistory
from .serializers import ViewHistoryCreateSerializer, ViewHistorySerializer


class ViewHistoryView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/sessions/{session_id}/history — 관람 기록 저장",
        request_body=ViewHistoryCreateSerializer,
        responses={
            201: openapi.Response('관람 기록 저장 성공', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'session_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'artifact_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'visited_at': openapi.Schema(type=openapi.TYPE_STRING),
                }
            )),
            400: '잘못된 요청',
            404: '세션 또는 유물 없음',
        }
    )
    def post(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return Response({'error': '세션을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ViewHistoryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        artifact_id = serializer.validated_data['artifact_id']
        try:
            artifact = Artifact.objects.get(cleveland_id=artifact_id)
        except Artifact.DoesNotExist:
            return Response({'error': '유물을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        record = ViewHistory.objects.create(session=session, artifact=artifact)

        # 히스토리 저장 후 세션 임베딩 자동 갱신
        viewed_artifact_ids = ViewHistory.objects.filter(
            session_id=session_id,
        ).values_list('artifact_id', flat=True)
        artifacts_with_vec = Artifact.objects.filter(
            id__in=viewed_artifact_ids,
            embedding_vector__isnull=False,
        )
        vectors = [a.embedding_vector for a in artifacts_with_vec if a.embedding_vector]
        if vectors:
            avg_vector = np.mean(np.array(vectors, dtype=np.float32), axis=0).tolist()
            session.history_embedding = avg_vector
            session.save(update_fields=['history_embedding'])

        return Response({
            'id': record.id,
            'session_id': session_id,
            'artifact_id': artifact_id,
            'visited_at': record.visited_at,
        }, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_description="GET /api/sessions/{session_id}/history — 관람 기록 목록 조회",
        responses={
            200: ViewHistorySerializer(many=True),
            404: '세션 없음',
        }
    )
    def get(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return Response({'error': '세션을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        records = ViewHistory.objects.filter(session=session).select_related('artifact')
        return Response({'history': ViewHistorySerializer(records, many=True).data})
