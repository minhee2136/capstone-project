from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import User
from .serializers import UserCreateSerializer, UserDetailSerializer


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


class UserDetailView(APIView):

    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_description="GET /api/users/{user_id}/ — 사용자 프로필 조회",
        responses={
            200: UserDetailSerializer,
            404: '사용자 없음',
        }
    )
    def get(self, request, user_id):
        user = self.get_user(user_id)
        if user is None:
            return Response({'error': '사용자를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserDetailSerializer(user).data)

    @swagger_auto_schema(
        operation_description="PUT /api/users/{user_id}/ — 사용자 프로필 수정 (수정할 필드만 전송)",
        request_body=UserDetailSerializer,
        responses={
            200: UserDetailSerializer,
            400: '잘못된 요청',
            404: '사용자 없음',
        }
    )
    def put(self, request, user_id):
        user = self.get_user(user_id)
        if user is None:
            return Response({'error': '사용자를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserDetailSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(UserDetailSerializer(user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
