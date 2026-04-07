import json
import numpy as np
from django.utils.timezone import now
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from openai import OpenAI
from django.conf import settings
from sentence_transformers import SentenceTransformer

from .models import Session
from .serializers import SessionCreateSerializer
from chat.models import Feedback
from artifacts.models import Artifact
from history.models import ViewHistory

gpt_client = OpenAI(api_key=settings.OPENAI_API_KEY)
embedding_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


def _get_session_or_404(session_id):
    try:
        return Session.objects.get(id=session_id), None
    except Session.DoesNotExist:
        return None, Response({'error': '세션을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)


def _get_view_history(session_id):
    return ViewHistory.objects.filter(session_id=session_id).select_related('artifact').order_by('visited_at')


class SessionView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/sessions/ — 세션 생성",
        request_body=SessionCreateSerializer,
        responses={201: "세션 생성 성공"},
    )
    def post(self, request):
        from users.models import User
        user_id = request.data.get('user_id')
        if user_id and not User.objects.filter(id=user_id).exists():
            return Response({'error': '존재하지 않는 user_id입니다.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SessionCreateSerializer(data=request.data)
        if serializer.is_valid():
            session = serializer.save()

            if session.user and session.interest_tags:
                text = ', '.join(session.interest_tags)
                embedding = embedding_model.encode(text).tolist()
                user.interest_embedding = embedding
                user.save(update_fields=['interest_embedding'])

            return Response(
                SessionCreateSerializer(session).data,
                status=status.HTTP_201_CREATED,
            )

            return Response(
                SessionCreateSerializer(session).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SessionDetailView(APIView):

    @swagger_auto_schema(
        operation_description="GET /api/sessions/{session_id}/ — 세션 조회 (context 포함)",
        responses={
            200: openapi.Response('세션 조회 성공', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'session_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'interest_tags': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)),
                    'knowledge_level': openapi.Schema(type=openapi.TYPE_STRING),
                    'view_time': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'artifact_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'context_summary': openapi.Schema(type=openapi.TYPE_STRING),
                }
            )),
            404: '세션 없음',
        }
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
            except Exception as e:
                data['context_summary'] = ''
        else:
            data['context_summary'] = ''

        return Response(data)



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


class SessionEndView(APIView):

    @swagger_auto_schema(
        operation_description="PUT /api/sessions/{session_id}/end/ — 세션 종료",
        responses={
            200: openapi.Response('세션 종료 성공', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'session_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'ended_at': openapi.Schema(type=openapi.TYPE_STRING),
                }
            )),
            404: '세션 없음',
        }
    )
    def put(self, request, session_id):
        session, err = _get_session_or_404(session_id)
        if err:
            return err
        session.ended_at = now()
        session.is_active = False
        session.save(update_fields=['ended_at', 'is_active'])
        return Response({'session_id': session_id, 'ended_at': session.ended_at})


class SessionLocationView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/sessions/{session_id}/location/ — 현재 위치(전시실 번호) 저장",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['gallery_number'],
            properties={'gallery_number': openapi.Schema(type=openapi.TYPE_STRING)},
        ),
        responses={
            200: openapi.Response('위치 저장 성공', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'session_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'current_location': openapi.Schema(type=openapi.TYPE_STRING),
                }
            )),
            400: '잘못된 요청',
            404: '세션 없음',
        }
    )
    def post(self, request, session_id):
        session, err = _get_session_or_404(session_id)
        if err:
            return err
        gallery_number = request.data.get('gallery_number', '')
        if not gallery_number:
            return Response({'error': 'gallery_number가 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)
        session.current_location = gallery_number
        session.save(update_fields=['current_location'])
        return Response({'session_id': session_id, 'current_location': session.current_location})


class SessionSummaryView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/sessions/{session_id}/summary/ — 전체 관람 요약 + 스토리텔링 스크립트 GPT 생성",
        responses={200: '요약 및 스크립트 생성 성공', 404: '세션 없음'},
    )
    def post(self, request, session_id):
        session, err = _get_session_or_404(session_id)
        if err:
            return err
        histories = _get_view_history(session_id)

        artifact_list_summary = '\n'.join([f"- {h.artifact.title} ({h.artifact.culture} / {h.artifact.technique})" for h in histories])
        summary_prompt = (
            f"사용자가 오늘 박물관에서 아래 유물들을 관람했어:\n{artifact_list_summary}\n\n"
            f"관람 시간: {session.view_time_minutes}분\n"
            f"관심 키워드: {session.interest_tags}\n"
            f"지식 수준: {session.knowledge_level}\n\n"
            f"전체 관람을 2-3문장으로 요약해줘. 한국어로 답해줘."
        )
        try:
            resp = gpt_client.chat.completions.create(
                model=settings.GPT_MODEL,
                messages=[{"role": "user", "content": summary_prompt}],
            )
            summary = resp.choices[0].message.content
        except Exception as e:
            return Response({'error': f'GPT 호출 실패: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        artifact_list_script = '\n'.join([f"{i+1}. {h.artifact.title}" for i, h in enumerate(histories)])
        script_prompt = (
            f"사용자가 아래 순서로 유물을 관람했어:\n{artifact_list_script}\n\n"
            f"이 관람 여정을 마치 박물관 가이드가 설명하듯 스토리텔링 형식으로 작성해줘. "
            f"각 유물 간의 연결성을 자연스럽게 이어줘. 한국어로 답해줘."
        )
        try:
            resp = gpt_client.chat.completions.create(
                model=settings.GPT_MODEL,
                messages=[{"role": "user", "content": script_prompt}],
            )
            script = resp.choices[0].message.content
        except Exception as e:
            return Response({'error': f'GPT 호출 실패: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'session_id': session_id,
            'artifact_count': len(histories),
            'view_time_minutes': session.view_time_minutes,
            'summary': summary,
            'script': script,
        })


class SessionSummaryNextTopicsView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/sessions/{session_id}/summary/next-topics/ — 다음 관람 주제 추천 GPT 생성",
        responses={200: '주제 추천 성공', 404: '세션 없음'},
    )
    def post(self, request, session_id):
        session, err = _get_session_or_404(session_id)
        if err:
            return err
        histories = _get_view_history(session_id)
        artifact_list = ', '.join([h.artifact.title for h in histories])
        prompt = (
            f"사용자가 오늘 관람한 유물들: {artifact_list}\n\n"
            f"이 관람 패턴을 바탕으로 다음 방문 시 관람하면 좋을 주제나 키워드를 3가지 추천해줘. "
            f"각 추천에 이유를 한 문장으로 설명해줘. 한국어로 답해줘.\n"
            f'JSON 형식으로만 반환해줘: [{{"topic": "주제", "reason": "이유"}}]'
        )
        try:
            resp = gpt_client.chat.completions.create(
                model=settings.GPT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.choices[0].message.content
            start, end = raw.find('['), raw.rfind(']') + 1
            next_topics = json.loads(raw[start:end]) if start != -1 else []
        except Exception as e:
            return Response({'error': f'GPT 호출 실패: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'session_id': session_id, 'next_topics': next_topics})


class SessionSummaryShareView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/sessions/{session_id}/summary/share/ — SNS 공유용 텍스트 GPT 생성",
        responses={200: '공유 텍스트 생성 성공', 404: '세션 없음'},
    )
    def post(self, request, session_id):
        session, err = _get_session_or_404(session_id)
        if err:
            return err
        histories = _get_view_history(session_id)
        artifact_count = len(histories)
        artifact_list = ', '.join([h.artifact.title for h in histories])
        prompt = (
            f"사용자가 오늘 {artifact_count}개의 유물을 관람했어.\n"
            f"관람한 유물들: {artifact_list}\n"
            f"SNS 공유용으로 짧고 감성적인 한 문장을 만들어줘. 이모지 포함. 한국어로 답해줘."
        )
        try:
            resp = gpt_client.chat.completions.create(
                model=settings.GPT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            share_text = resp.choices[0].message.content.strip()
        except Exception as e:
            return Response({'error': f'GPT 호출 실패: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'session_id': session_id, 'share_text': share_text})