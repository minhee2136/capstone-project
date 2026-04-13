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
from history.models import ViewHistory
from chat.models import Message
from artifacts.models import Artifact

gpt_client = OpenAI(api_key=settings.OPENAI_API_KEY)
embedding_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


def _get_view_history(session_id):
    return ViewHistory.objects.filter(session_id=session_id).select_related('artifact').order_by('visited_at')


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
        operation_summary= "새션 조회",
    )
    def get(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return Response({'error': '세션을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        data = SessionCreateSerializer(session).data
        histories = _get_view_history(session_id)
        data['artifact_count'] = len(histories)

        if histories:
            artifact_list = '\n'.join([
                f"- {h.artifact.title} ({h.artifact.department} / {h.artifact.culture} / {h.artifact.technique})"
                for h in histories
            ])
            prompt = f"다음은 사용자가 관람한 유물 목록이야:\n{artifact_list}\n\n이 관람 흐름에서 주요 테마와 관심사를 2-3문장으로 분석해줘. 한국어로 답해줘."
            try:
                resp = gpt_client.chat.completions.create(
                    model=settings.GPT_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                )
                data['context_summary'] = resp.choices[0].message.content
            except Exception:
                data['context_summary'] = ''
        else:
            data['context_summary'] = ''

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

        messages = Message.objects.filter(
            session=session,
            role=Message.Role.ASSISTANT,
            artifact_id__isnull=False,
        ).order_by('created_at')

        seen = set()
        recommended_ids = []
        for msg in messages:
            if msg.artifact_id not in seen:
                seen.add(msg.artifact_id)
                recommended_ids.append(msg.artifact_id)
                
        artifact_map = {
            a.cleveland_id: a
            for a in Artifact.objects.filter(cleveland_id__in=recommended_ids)
        }

        artifacts = []
        for aid in recommended_ids:
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
