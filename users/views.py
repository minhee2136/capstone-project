from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import User
from .serializers import UserCreateSerializer


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