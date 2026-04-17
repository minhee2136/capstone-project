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


class ArtifactAiDescriptionView(APIView):
    @swagger_auto_schema(
        operation_summary="AI 유물 설명 생성",
        responses={200: openapi.Response('AI 생성 설명', schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'artifact_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'ai_description': openapi.Schema(type=openapi.TYPE_STRING),
            }
        ))}
    )
    def get(self, request, artifact_id):
        try:
            artifact = Artifact.objects.get(cleveland_id=artifact_id)
        except Artifact.DoesNotExist:
            return Response({'error': '유물을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        # 기존 설명이 있으면 그것을 요약 및 보강하거나, 없으면 기본 정보로 생성
        base_info = f"제목: {artifact.title}\n종류: {artifact.type}\n제작 시기: {artifact.creation_date}\n문화/국가: {artifact.culture}\n"
        if artifact.description:
            base_info += f"기존 설명: {artifact.description}\n"
        if artifact.did_you_know:
            base_info += f"참고 지식: {artifact.did_you_know}\n"

        prompt = (
            f"당신은 박물관의 전문 전시 해설사(도슨트)입니다. 아래 유물 정보를 바탕으로 관람객에게 깊이 있게 설명하듯 4~6문장의 상세하고 풍성한 한국어 해설을 작성해 주세요.\n\n"
            f"[유물 정보]\n{base_info}\n\n"
            f"[엄격한 작성 규칙 - 반드시 지키세요]\n"
            f"1. **언어 제한**: 출력은 100% 순수 '한글'로만 작성하세요. **한자(漢字)**(예: 太陽神, 崇拜), 영어, 러시아어, 일본어 등 한글을 제외한 다른 문자는 단 한 글자도 포함되어선 안 됩니다. 한자로 쓰이는 단어라도 무조건 한글로만 적으세요 (예시: 太陽神 -> 태양신, 寶石 -> 보석).\n"
            f"2. 문체는 반드시 전문적이고 정중한 격식체(~습니다, ~입니다, ~했습니다)만을 사용하세요.\n"
            f"3. '이 유물은 ~입니다'와 같은 서두는 생략하고, 작품의 역사적 배경, 기법, 의미 등 내용으로 바로 진입하세요.\n"
            f"4. 영문 정보는 직역하지 말고 어색한 번역투가 남지 않도록 완전히 한국어다운 문장으로 자연스럽게 의역하세요. 번역기 특유의 현상이나 외국어가 문장 중간에 혼용되는 일이 절대 없어야 합니다.\n"
            f"5. 같은 의미나 동일한 단어를 불필요하게 반복하지 마세요."
        )

        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500,
            )
            ai_desc = completion.choices[0].message.content.strip()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Groq API 에러: {e}")
            ai_desc = f"AI 설명을 생성하는 중 문제가 발생했습니다. ({str(e)[:50]}...)"

        return Response({
            'artifact_id': artifact.cleveland_id,
            'ai_description': ai_desc
        })

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


