from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from sentence_transformers import SentenceTransformer

from .models import User
from .serializers import UserCreateSerializer, InterestEmbeddingSerializer

_embedding_model = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
        )
    return _embedding_model


class UserView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/users/ — 사용자 생성",
        request_body=UserCreateSerializer,
        responses={201: "사용자 생성 성공"},
    )
    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                UserCreateSerializer(user).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserInterestEmbeddingView(APIView):

    @swagger_auto_schema(
        operation_description="POST /api/users/{user_id}/interest-embedding — 관심사 임베딩 생성 및 저장",
        request_body=InterestEmbeddingSerializer,
        responses={
            200: openapi.Response('임베딩 생성 성공', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'embedding_generated': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                }
            )),
            400: '잘못된 요청',
            404: '사용자 없음',
        }
    )
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': '사용자를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = InterestEmbeddingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        interest_tags = serializer.validated_data['interest_tags']
        knowledge_level = serializer.validated_data['knowledge_level']

        embedding_text = ' '.join(interest_tags)
        model = get_embedding_model()
        vector = model.encode(embedding_text).tolist()

        user.interest_tags = interest_tags
        user.knowledge_level = knowledge_level
        user.interest_embedding = vector
        user.save(update_fields=['interest_tags', 'knowledge_level', 'interest_embedding', 'updated_at'])

        return Response({'user_id': user.id, 'embedding_generated': True}, status=status.HTTP_200_OK)