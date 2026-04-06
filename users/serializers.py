from rest_framework import serializers
from .models import User


class UserCreateSerializer(serializers.ModelSerializer):
    """POST /api/users/ — 사용자 생성"""

    class Meta:
        model = User
        fields = ['id', 'nickname', 'gender', 'birth_year']

    def to_representation(self, instance):
        return {
            'code': 201,
            'user_id': instance.id,
            'nickname': instance.nickname,
            'gender': instance.gender,
            'birthyear': instance.birth_year,
        }