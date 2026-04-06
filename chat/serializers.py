from rest_framework import serializers
from .models import Message, Feedback


class MessageCreateSerializer(serializers.Serializer):
    """POST /api/chat/{session_id}/messages/ — 채팅 메시지 전송"""
    message = serializers.CharField()


class MessageSerializer(serializers.ModelSerializer):
    """GET /api/chat/{session_id}/messages/ — 채팅 히스토리 조회"""

    artifact = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'role', 'content', 'artifact', 'created_at']

    def get_artifact(self, obj):
        if obj.artifact_id is None:
            return None
        from artifacts.models import Artifact
        try:
            artifact = Artifact.objects.get(id=obj.artifact_id)
            return {
                'artifact_id': artifact.id,
                'title': artifact.title,
                'image_url': artifact.image_url,
                'location': artifact.location,
                'reason': artifact.reason if hasattr(artifact, 'reason') else '',
            }
        except Artifact.DoesNotExist:
            return None


class FeedbackCreateSerializer(serializers.ModelSerializer):
    """POST /api/recommendations/{rec_id}/feedback/ — 피드백 제출"""

    class Meta:
        model = Feedback
        fields = ['feedback_type']

    def to_representation(self, instance):
        return {
            'code': 201,
            'user_id': instance.session.user.id,
            'session_id': instance.session.id,
            'feedback_id': instance.id,
        }