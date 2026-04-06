from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from openai import OpenAI
from django.conf import settings

from sessions.models import Session
from .models import Message, Feedback
from .serializers import MessageCreateSerializer, MessageSerializer, FeedbackCreateSerializer


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