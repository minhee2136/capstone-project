from rest_framework import serializers
from .models import Artifact


class ArtifactDetailSerializer(serializers.ModelSerializer):
    """GET /api/artifacts/{artifact_id}/ — 유물 상세 정보 조회"""

    artifact_id = serializers.IntegerField(source='cleveland_id')

    class Meta:
        model = Artifact
        fields = [
            'artifact_id',
            'title',
            'type',
            'department',
            'collection',
            'technique',
            'culture',
            'creation_date_earliest',
            'creation_date_latest',
            'current_location',
            'image_url',
            'description',
            'did_you_know',
        ]


class ArtifactDescriptionSerializer(serializers.Serializer):
    """POST /api/artifacts/{artifact_id}/description/ — 맞춤 설명 + 연결 유물 생성"""
    session_id = serializers.IntegerField()
