from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.http import Http404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .services import calculate_optimal_path
from chat.models import Chat
from sessions.models import Session

class RecommendPathView(APIView):
    @swagger_auto_schema(
        operation_summary="히스토리 기반 동적 맞춤형 전체 경로 추천",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'chat_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="채팅 ID"),
                'session_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="세션 ID"),
            },
            required=['chat_id', 'session_id']
        ),
        responses={200: "성공"}
    )
    def post(self, request):
        chat_id = request.data.get('chat_id')
        session_id = request.data.get('session_id')
        
        if not chat_id or not session_id:
            return Response({"error": "chat_id와 session_id 필드가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            # 채팅 히스토리 및 세션 정보 로드
            chat = get_object_or_404(Chat, id=chat_id)
            session = get_object_or_404(Session, id=session_id)
            
            # 사용자 관심사 및 남은 시간 파악 (기본 60분)
            user_interest = session.interest_tag if session.interest_tag else " ".join(session.interest_tags)
            if not user_interest:
                user_interest = "art" # 관심사가 없을 경우 기본값
                
            time_limit = session.view_time_minutes if session.view_time_minutes else 60
            
            # 파싱: chat.history는 dict 형태의 리스트({ "artifact_id": 123, ... })일 수 있으므로 정수 ID만 추출
            raw_history = chat.history if hasattr(chat, 'history') and chat.history else []
            history_ids = []
            for item in raw_history:
                if isinstance(item, dict) and 'artifact_id' in item:
                    history_ids.append(item['artifact_id'])
                elif isinstance(item, int):
                    history_ids.append(item)
            
            # 서비스 함수 호출 (Gurobi 모형 실행)
            result = calculate_optimal_path(
                user_interest=user_interest,
                t_total=int(time_limit),
                history=history_ids
            )
            
            if result.get("status") == "success":
                # 프론트엔드가 요구하는 형태로 포맷팅
                recommendations = []
                for item in result.get("path", []):
                    # 이동 시간 (cost = 이동시간 + 관람시간 4분 이므로 이동시간은 cost - 4)
                    move_time = max(0, item["step_time"] - 4.0) if item["step_time"] > 0 else 0
                    
                    recommendations.append({
                        "artifact_id": item["artifact_id"],
                        "title": item["title"],
                        "description": item.get("department", "추천 유물입니다."),
                        "image_url": item["image_url"],
                        "current_location": item["current_location"],
                        "route_guide": {
                            "origin": item["prev_location"],
                            "destination": item["current_location"],
                            "estimated_time": f"약 {move_time}분",
                            "estimated_distance": "가까운 거리" if move_time <= 1.0 else "중간 거리",
                            "instruction": f"{item['prev_location']}에서 {item['current_location']} 전시실 방향으로 이동해 주세요."
                        }
                    })
                
                response_data = {
                    "status": "success",
                    "total_time_minutes": result.get("total_time_minutes"),
                    "path_length": result.get("path_length"),
                    "recommendations": recommendations
                }
                
                return Response(response_data, status=status.HTTP_200_OK)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
                
        except Http404:
            return Response({"error": "해당 chat_id 또는 session_id를 찾을 수 없습니다. (데이터베이스에 없음)"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
