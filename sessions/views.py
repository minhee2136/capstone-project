import numpy as np
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Session
from .serializers import SessionCreateSerializer
from chat.models import Feedback
from artifacts.models import Artifact


class SessionView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/sessions/ — 세션 생성",
        request_body=SessionCreateSerializer,
        responses={201: "세션 생성 성공"},
    )
    def post(self, request):
        serializer = SessionCreateSerializer(data=request.data)
        if serializer.is_valid():
            session = serializer.save()
            return Response(
                SessionCreateSerializer(session).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SessionHistoryEmbeddingView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/sessions/{session_id}/history-embedding — 관람완료 유물 기반 히스토리 임베딩 생성",
        responses={
            200: openapi.Response('임베딩 생성 결과', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'session_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'artifact_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'embedding_generated': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                }
            )),
            404: '세션 없음',
        }
    )
    def post(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return Response({'error': '세션을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        liked_artifact_ids = Feedback.objects.filter(
            session_id=session_id,
            feedback_type=Feedback.FeedbackType.LIKE,
        ).values_list('artifact_id', flat=True)

        if not liked_artifact_ids:
            return Response({'session_id': session_id, 'artifact_count': 0, 'embedding_generated': False})

        artifacts = Artifact.objects.filter(
            cleveland_id__in=liked_artifact_ids,
            embedding_vector__isnull=False,
        )

        vectors = [a.embedding_vector for a in artifacts if a.embedding_vector]
        if not vectors:
            return Response({'session_id': session_id, 'artifact_count': 0, 'embedding_generated': False})

        avg_vector = np.mean(np.array(vectors, dtype=np.float32), axis=0).tolist()
        session.history_embedding = avg_vector
        session.save(update_fields=['history_embedding'])

        return Response({
            'session_id': session_id,
            'artifact_count': len(vectors),
            'embedding_generated': True,
        })


class SessionCandidatesView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/sessions/{session_id}/candidates — 코사인 유사도 기반 추천 유물 Top 10",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={'mode': openapi.Schema(type=openapi.TYPE_STRING, default='recommendation')},
        ),
        responses={
            200: openapi.Response('추천 후보 목록', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'candidates': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_OBJECT),
                    )
                }
            )),
            400: '임베딩 없음',
            404: '세션 없음',
        }
    )
    def post(self, request, session_id):
        try:
            session = Session.objects.select_related('user').get(id=session_id)
        except Session.DoesNotExist:
            return Response({'error': '세션을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        user = session.user
        interest_vec = np.array(user.interest_embedding, dtype=np.float32) if user.interest_embedding else None
        history_vec = np.array(session.history_embedding, dtype=np.float32) if session.history_embedding else None

        if interest_vec is None and history_vec is None:
            return Response({'error': '임베딩이 없습니다. 먼저 interest-embedding을 생성하세요.'}, status=status.HTTP_400_BAD_REQUEST)

        if interest_vec is not None and history_vec is not None:
            query_vec = (interest_vec + history_vec) / 2.0
        elif history_vec is not None:
            query_vec = history_vec
        else:
            query_vec = interest_vec

        # 이미 좋아요 누른 유물 제외
        liked_ids = set(Feedback.objects.filter(
            session_id=session_id,
            feedback_type=Feedback.FeedbackType.LIKE,
        ).values_list('artifact_id', flat=True))

        artifacts = Artifact.objects.filter(is_active=True, embedding_vector__isnull=False)

        # 코사인 유사도 계산
        results = []
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return Response({'error': '쿼리 벡터가 zero vector입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        for artifact in artifacts:
            if artifact.cleveland_id in liked_ids:
                continue
            vec = np.array(artifact.embedding_vector, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm == 0:
                continue
            score = float(np.dot(query_vec, vec) / (query_norm * norm))
            results.append((score, artifact))

        results.sort(key=lambda x: x[0], reverse=True)
        top10 = results[:10]

        candidates = [
            {
                'artifact_id': a.cleveland_id,
                'title': a.title,
                'current_location': a.current_location,
                'similarity_score': round(score, 4),
                'image_url': a.image_url,
            }
            for score, a in top10
        ]

        return Response({'candidates': candidates})