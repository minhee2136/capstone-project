from rest_framework import serializers
from .models import Session


class SessionCreateSerializer(serializers.ModelSerializer):
    """POST /api/sessions/ — 세션 생성"""

    user_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Session
        fields = ['user_id', 'interest_tags', 'knowledge_level', 'view_time_minutes']

    def validate_user_id(self, value):
        from users.models import User
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("존재하지 않는 user_id입니다.")
        return value

    def create(self, validated_data):
        from users.models import User
        user = User.objects.get(id=validated_data.pop('user_id'))
        return Session.objects.create(user=user, **validated_data)

    def to_representation(self, instance):
        return {
            'code': 201,
            'user_id': instance.user.id,
            'session_id': instance.id,
            'interest_tags': instance.interest_tags,
            'knowledge_level': instance.knowledge_level,
            'view_time': instance.view_time_minutes,
        }