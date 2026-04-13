from rest_framework import serializers
from .models import User


GENDER_ALIAS = {
    '남자': 'M', '남성': 'M', 'male': 'M', 'Male': 'M', 'MALE': 'M', 'm': 'M',
    '여자': 'F', '여성': 'F', 'female': 'F', 'Female': 'F', 'FEMALE': 'F', 'f': 'F',
}


class UserCreateSerializer(serializers.ModelSerializer):
    """POST /api/users/ — 사용자 생성"""

    gender = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = User
        fields = ['id', 'nickname', 'gender', 'birth_year']

    def validate_gender(self, value):
        converted = GENDER_ALIAS.get(value, value)
        if converted not in ('M', 'F', 'N'):
            raise serializers.ValidationError(f"'{value}'은(는) 유효하지 않은 성별입니다. 남자/여자/M/F/N 중 하나를 입력하세요.")
        return converted

    def to_representation(self, instance):
        return {
            'user_id': instance.id,
            'nickname': instance.nickname,
            'gender': instance.gender,
            'birth_year': instance.birth_year,
        }


class UserDetailSerializer(serializers.ModelSerializer):
    """GET/PUT /api/users/{user_id} — 프로필 조회/수정"""

    gender = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def validate_gender(self, value):
        converted = GENDER_ALIAS.get(value, value)
        if converted not in ('M', 'F', 'N'):
            raise serializers.ValidationError(f"'{value}'은(는) 유효하지 않은 성별입니다. 남자/여자/M/F/N 중 하나를 입력하세요.")
        return converted

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