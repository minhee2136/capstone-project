from rest_framework import serializers
from .models import User


class UserCreateSerializer(serializers.ModelSerializer):
    """POST /api/users/ — 사용자 생성"""

    class Meta:
        model = User
        fields = ['id', 'nickname', 'gender', 'birth_year']

    def to_representation(self, instance):
        return {
            'user_id': instance.id,
            'nickname': instance.nickname,
            'gender': instance.gender,
            'birth_year': instance.birth_year,
        }


class UserDetailSerializer(serializers.ModelSerializer):
    """GET/PUT /api/users/{user_id} — 프로필 조회/수정"""

    class Meta:
        model = User
        fields = ['id', 'nickname', 'gender', 'birth_year']
        extra_kwargs = {
            'nickname': {'required': False},
            'gender': {'required': False},
            'birth_year': {'required': False},
        }

    def to_representation(self, instance):
        return {
            'user_id': instance.id,
            'nickname': instance.nickname,
            'gender': instance.gender,
            'birth_year': instance.birth_year,
        }