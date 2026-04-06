from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema

from .serializers import SessionCreateSerializer


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