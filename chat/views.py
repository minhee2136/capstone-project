import random
import re
import numpy as np
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from openai import OpenAI
from django.conf import settings
from sentence_transformers import SentenceTransformer

from sessions.models import Session
from artifacts.models import Artifact
from .models import Chat, Message, Feedback
from .serializers import MessageCreateSerializer, MessageSerializer, FeedbackCreateSerializer

embedding_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

CONN_MESSAGES = {
    "story":    "이전 작품과 같은 흐름으로 이어지는 작품이에요.",
    "mystery":  "전혀 다를 것 같지만, 의외의 연결이 있어요.",
    "contrast": "취향을 반영해서 방향을 바꿔볼게요.",
    "shock":    "지나치기 아쉬운 작품이 근처에 있어요.",
}


def _get_chat_or_404(chat_id):
    try:
        return Chat.objects.select_related('session').get(id=chat_id), None
    except Chat.DoesNotExist:
        return None, Response({'error': '채팅을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)


def _decide_conn_type(similarity_score, feedback_history, history_count):
    recent = feedback_history[-2:]
    if any(f == -1 for f in recent):
        return "contrast"
    if history_count < 3:
        return "story"
    if similarity_score >= 0.85:
        return "mystery"
    if 0.6 <= similarity_score < 0.85:
        return "story"
    return "shock"


def _gallery_number(location: str) -> int:
    m = re.match(r'(\d+)', location.strip())
    return int(m.group(1)) if m else -1


def _cosine_scores(query_vec, candidates):
    scored = []
    for artifact in candidates:
        vec = np.array(artifact.embedding_vector, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm == 0:
            continue
        score = float(np.dot(query_vec, vec / norm))
        scored.append((score, artifact))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


class ChatMessageView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/chat/{session_id}/messages/ — 채팅 메시지 전송",
        request_body=MessageCreateSerializer,
        responses={201: "메시지 전송 성공"},
    )
    def post(self, request, session_id):
        session = get_object_or_404(Session, id=session_id)
        serializer = MessageCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_message = serializer.validated_data['message']

        # 사용자 메시지 저장
        Message.objects.create(
            session=session,
            role=Message.Role.USER,
            content=user_message,
        )

        # 이전 대화 히스토리 조회
        history = Message.objects.filter(session=session).order_by('created_at')
        gpt_messages = [
            {
                "role": "system",
                "content": (
                    f"당신은 뮤지엄 큐레이터입니다. "
                    f"사용자의 관심사: {session.interest_tags}, "
                    f"지식 수준: {session.knowledge_level}, "
                    f"관람 희망 시간: {session.view_time_minutes}분. "
                    f"사용자 맞춤형 유물을 추천하고 설명해주세요."
                )
            }
        ]
        for msg in history:
            gpt_messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        # GPT-4o-mini 호출
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        gpt_response = client.chat.completions.create(
            model=settings.GPT_MODEL,
            messages=gpt_messages,
        )
        assistant_content = gpt_response.choices[0].message.content

        # 어시스턴트 메시지 저장
        assistant_message = Message.objects.create(
            session=session,
            role=Message.Role.ASSISTANT,
            content=assistant_content,
        )

        return Response(
            {
                'message_id': assistant_message.id,
                'role': assistant_message.role,
                'content': assistant_message.content,
                'artifact': None,
                'created_at': assistant_message.created_at,
            },
            status=status.HTTP_201_CREATED,
        )

    @swagger_auto_schema(
        operation_description="GET /api/chat/{session_id}/messages/ — 채팅 히스토리 조회",
        responses={200: "채팅 히스토리 조회 성공"},
    )
    def get(self, request, session_id):
        session = get_object_or_404(Session, id=session_id)
        messages = Message.objects.filter(session=session).order_by('created_at')
        serializer = MessageSerializer(messages, many=True)
        return Response({'messages': serializer.data})


class FeedbackView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/recommendations/{rec_id}/feedback/ — 피드백 제출",
        request_body=FeedbackCreateSerializer,
        responses={201: "피드백 제출 성공"},
    )
    def post(self, request, rec_id):
        session = get_object_or_404(Session, id=request.data.get('session_id'))
        serializer = FeedbackCreateSerializer(data=request.data)

        if serializer.is_valid():
            feedback = Feedback.objects.create(
                session=session,
                artifact_id=rec_id,
                feedback_type=serializer.validated_data['feedback_type'],
            )
            return Response(
                FeedbackCreateSerializer(feedback).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ── Chat 기반 API ──────────────────────────────────────────────────────────────

class ChatCreateView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/chats/ — 채팅 생성",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['session_id'],
            properties={'session_id': openapi.Schema(type=openapi.TYPE_INTEGER)},
        ),
        responses={201: openapi.Response('채팅 생성 성공', schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'chat_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'session_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'created_at': openapi.Schema(type=openapi.TYPE_STRING),
            },
        ))},
    )
    def post(self, request):
        session = get_object_or_404(Session, id=request.data.get('session_id'))
        chat = Chat.objects.create(session=session)
        return Response(
            {
                'chat_id': chat.id,
                'session_id': chat.session_id,
                'created_at': chat.created_at.isoformat().replace('+00:00', 'Z'),
            },
            status=status.HTTP_201_CREATED,
        )


class ChatRecommendationsView(generics.RetrieveAPIView):

    @swagger_auto_schema(
        operation_description="GET /api/chats/{chat_id}/recommendations/ — 유물 추천 (상위 5개)",
        responses={
            200: openapi.Response('추천 목록', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'chat_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'recommendations': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                },
            )),
            400: '임베딩 생성 불가',
            404: '채팅 없음',
        },
    )
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def retrieve(self, _request, *_args, **_kwargs):
        chat_id = self.kwargs['chat_id']
        chat, err = _get_chat_or_404(chat_id)
        if err:
            return err

        session = chat.session
        interest_keywords = session.interest_tags or []
        interest_tag = session.interest_tag

        if interest_keywords:
            candidate_qs = Artifact.objects.filter(
                keyword__in=interest_keywords,
                embedding_vector__isnull=False,
            )
        else:
            candidate_qs = Artifact.objects.filter(embedding_vector__isnull=False)

        viewed_ids = set(chat.history)
        candidates = [a for a in candidate_qs if a.id not in viewed_ids]

        if not candidates:
            return Response({'chat_id': chat_id, 'recommendations': []})

        if interest_tag:
            query_vec = embedding_model.encode(interest_tag).astype(np.float32)
        else:
            vecs = np.array([a.embedding_vector for a in candidates], dtype=np.float32)
            query_vec = vecs.mean(axis=0)

        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return Response({'error': '쿼리 벡터가 zero vector입니다.'}, status=status.HTTP_400_BAD_REQUEST)
        query_vec = query_vec / query_norm

        scored = _cosine_scores(query_vec, candidates)
        recommendations = [
            {
                'artifact_id': a.cleveland_id,
                'title': a.title,
                'type': a.type,
                'current_location': a.current_location,
                'image_url': a.image_url,
                'similarity_score': round(score, 4),
            }
            for score, a in scored[:5]
        ]
        return Response({'chat_id': chat_id, 'recommendations': recommendations})


class ChatFeedbackView(generics.CreateAPIView):

    @swagger_auto_schema(
        operation_description="POST /api/chats/{chat_id}/feedback/ — 유물 피드백 (1: 흥미로워요, -1: 별로예요)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['artifact_id', 'feedback'],
            properties={
                'artifact_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'feedback': openapi.Schema(type=openapi.TYPE_INTEGER, description='1 또는 -1'),
            },
        ),
        responses={
            201: openapi.Response('피드백 저장 성공', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'chat_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'artifact_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'feedback': openapi.Schema(type=openapi.TYPE_INTEGER),
                },
            )),
            400: '유효하지 않은 요청',
            404: '채팅 없음',
        },
    )
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def create(self, request, *_args, **_kwargs):
        chat_id = self.kwargs['chat_id']
        chat, err = _get_chat_or_404(chat_id)
        if err:
            return err

        artifact_id = request.data.get('artifact_id')
        feedback_int = request.data.get('feedback')

        if feedback_int not in (1, -1):
            return Response({'error': 'feedback은 1 또는 -1이어야 합니다.'}, status=status.HTTP_400_BAD_REQUEST)
        if not Artifact.objects.filter(cleveland_id=artifact_id).exists():
            return Response({'error': '존재하지 않는 artifact_id입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        chat.feedback_history = list(chat.feedback_history) + [feedback_int]
        chat.save(update_fields=['feedback_history'])

        return Response(
            {'chat_id': chat_id, 'artifact_id': artifact_id, 'feedback': feedback_int},
            status=status.HTTP_201_CREATED,
        )


class ChatNextRecommendationView(generics.RetrieveAPIView):

    @swagger_auto_schema(
        operation_description="GET /api/chats/{chat_id}/next-recommendation/ — 다음 유물 추천",
        responses={
            200: openapi.Response('다음 추천 유물', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'chat_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'artifact': openapi.Schema(type=openapi.TYPE_OBJECT),
                    'conn_type': openapi.Schema(type=openapi.TYPE_STRING),
                    'conn_message': openapi.Schema(type=openapi.TYPE_STRING),
                },
            )),
            400: '히스토리 없음 또는 임베딩 없음',
            404: '채팅 없음',
        },
    )
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def retrieve(self, _request, *_args, **_kwargs):
        chat_id = self.kwargs['chat_id']
        chat, err = _get_chat_or_404(chat_id)
        if err:
            return err

        if not chat.history:
            return Response(
                {'error': '관람 히스토리가 없습니다. 먼저 유물을 관람해주세요.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        viewed_artifacts = Artifact.objects.filter(id__in=chat.history, embedding_vector__isnull=False)
        history_vecs = [a.embedding_vector for a in viewed_artifacts]

        if not history_vecs:
            return Response({'error': '히스토리 유물에 임베딩 벡터가 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        query_vec = np.array(history_vecs, dtype=np.float32).mean(axis=0)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return Response({'error': '쿼리 벡터가 zero vector입니다.'}, status=status.HTTP_400_BAD_REQUEST)
        query_vec = query_vec / query_norm

        viewed_ids = set(chat.history)
        candidates = [
            a for a in Artifact.objects.filter(embedding_vector__isnull=False)
            if a.id not in viewed_ids
        ]
        if not candidates:
            return Response({'error': '추천 가능한 유물이 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        scored = _cosine_scores(query_vec, candidates)
        conn_type = _decide_conn_type(scored[0][0], list(chat.feedback_history), len(chat.history))

        if conn_type == "story":
            chosen_score, chosen = scored[0]
        elif conn_type == "mystery":
            n = len(scored)
            lo, hi = max(0, int(n * 0.30)), max(1, int(n * 0.60))
            chosen_score, chosen = random.choice(scored[lo:hi])
        elif conn_type == "contrast":
            chosen_score, chosen = scored[-1]
        else:  # shock
            session_gallery = _gallery_number(chat.session.current_location or "")
            if session_gallery >= 0:
                scored.sort(key=lambda x: abs(_gallery_number(x[1].current_location) - session_gallery))
            chosen_score, chosen = scored[0]

        chat.history = list(chat.history) + [chosen.id]
        chat.save(update_fields=['history'])

        return Response({
            'chat_id': chat_id,
            'artifact': {
                'artifact_id': chosen.cleveland_id,
                'title': chosen.title,
                'type': chosen.type,
                'current_location': chosen.current_location,
                'image_url': chosen.image_url,
                'similarity_score': round(chosen_score, 4),
            },
            'conn_type': conn_type,
            'conn_message': CONN_MESSAGES[conn_type],
        })
