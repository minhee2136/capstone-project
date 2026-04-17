from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from openai import OpenAI
from django.conf import settings
from sentence_transformers import SentenceTransformer

from .models import Session
from .serializers import SessionCreateSerializer, OnboardingSessionCreateSerializer
from chat.models import Message
from artifacts.models import Artifact

gpt_client = OpenAI(api_key=settings.OPENAI_API_KEY)
embedding_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")



class SessionView(APIView):

    @swagger_auto_schema(
        operation_summary="세션 생성",
    )
    def post(self, request):
        serializer = OnboardingSessionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        session = serializer.save()

        if session.interest_tags:
            text = ', '.join(session.interest_tags)
            embedding = embedding_model.encode(text).tolist()
            session.user.interest_embedding = embedding
            session.user.save(update_fields=['interest_embedding'])

        return Response(
            OnboardingSessionCreateSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )


class SessionDetailView(APIView):

    @swagger_auto_schema(
        operation_summary= "세션 조회",
    )
    def get(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return Response({'error': '세션을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        data = SessionCreateSerializer(session).data
        return Response(data)


class SessionHistorySummaryView(APIView):

    @swagger_auto_schema(
        operation_summary="관람 유물 히스토리 목록",
        
    )
    def get(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return Response({'error': '세션을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        # 세션에 연결된 모든 채팅의 히스토리(방문 기록)를 취합
        seen = set()
        visited_ids = []
        for chat in session.chats.all():
            for h in chat.history:
                aid = h.get('artifact_id') if isinstance(h, dict) else h
                if aid and aid not in seen:
                    seen.add(aid)
                    visited_ids.append(aid)

        artifact_map = {
            a.id: a
            for a in Artifact.objects.filter(id__in=visited_ids)
        }

        artifacts = []
        for aid in visited_ids:
            a = artifact_map.get(aid)
            if a:
                artifacts.append({
                    'artifact_id': a.cleveland_id,
                    'title': a.title,
                    'image_url': a.image_url,
                })

        return Response({
            'artifact_count': len(artifacts),
            'interest_topics': session.interest_tags or [],
            'artifacts': artifacts,
        })
