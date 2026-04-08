from rest_framework import serializers
from .models import Session

VALID_KEYWORDS = {"회화", "조각·공예", "전쟁·무기", "동양 문화", "신화·종교", "역사·기록"}
VALID_KNOWLEDGE_LEVELS = {"초급", "중급", "전문가"}


class OnboardingSessionCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    interest_keywords = serializers.ListField(
        child=serializers.CharField(), min_length=1
    )
    knowledge_level = serializers.CharField()
    visit_hour = serializers.IntegerField(default=0)
    visit_minute = serializers.IntegerField(default=0)
    interest_tag = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def validate_user_id(self, value):
        from users.models import User
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("존재하지 않는 user_id입니다.")
        return value

    def validate_interest_keywords(self, value):
        invalid = [kw for kw in value if kw not in VALID_KEYWORDS]
        if invalid:
            raise serializers.ValidationError(
                f"유효하지 않은 키워드: {invalid}. "
                f"허용 값: {sorted(VALID_KEYWORDS)}"
            )
        return value

    def validate_knowledge_level(self, value):
        if value not in VALID_KNOWLEDGE_LEVELS:
            raise serializers.ValidationError(
                f"유효하지 않은 지식 수준입니다. 허용 값: {sorted(VALID_KNOWLEDGE_LEVELS)}"
            )
        return value

    def validate(self, attrs):
        hour = attrs.get("visit_hour", 0)
        minute = attrs.get("visit_minute", 0)
        # 둘 다 0이면 "시간 상관없이" → null 저장
        if hour == 0 and minute == 0:
            attrs["visit_hour"] = None
            attrs["visit_minute"] = None
        return attrs

    def create(self, validated_data):
        from users.models import User
        user = User.objects.get(id=validated_data["user_id"])
        return Session.objects.create(
            user=user,
            interest_tags=validated_data["interest_keywords"],
            knowledge_level=validated_data["knowledge_level"],
            visit_hour=validated_data["visit_hour"],
            visit_minute=validated_data["visit_minute"],
            interest_tag=validated_data.get("interest_tag"),
        )

    def to_representation(self, instance):
        return {
            "session_id": instance.id,
            "user_id": instance.user_id,
            "interest_keywords": instance.interest_tags,
            "knowledge_level": instance.knowledge_level,
            "visit_hour": instance.visit_hour,
            "visit_minute": instance.visit_minute,
            "interest_tag": instance.interest_tag,
            "created_at": instance.created_at.isoformat().replace("+00:00", "Z"),
        }


class SessionFeedbackSerializer(serializers.Serializer):
    artifact_id = serializers.IntegerField()
    feedback = serializers.IntegerField()

    def validate_feedback(self, value):
        if value not in (1, -1):
            raise serializers.ValidationError("feedback은 1 또는 -1이어야 합니다.")
        return value

    def validate_artifact_id(self, value):
        from artifacts.models import Artifact
        if not Artifact.objects.filter(cleveland_id=value).exists():
            raise serializers.ValidationError("존재하지 않는 artifact_id입니다.")
        return value


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