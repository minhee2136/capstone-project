from rest_framework import serializers
from .models import Artifact


class ArtifactDetailSerializer(serializers.ModelSerializer):
    """GET /api/artifacts/{artifact_id}/ — 유물 상세 정보 조회"""

    class Meta:
        model = Artifact
        fields = [
            'id',
            'cleveland_id',
            'title',
            'type',
            'department',
            'culture',
            'technique',
            'creation_date_earliest',
            'creation_date_latest',
            'current_location',
            'image_url',
            'description',
            'did_you_know',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return {
            'artifact_id': data['id'],
            'cleveland_id': data['cleveland_id'],
            'title': data['title'],
            'type': data['type'],
            'department': data['department'],
            'culture': data['culture'],
            'technique': data['technique'],
            'period': f"{data['creation_date_earliest']} ~ {data['creation_date_latest']}",
            'location': data['current_location'],
            'image_url': data['image_url'],
            'description': data['description'],
            'did_you_know': data['did_you_know'],
        }


class ArtifactDescriptionSerializer(serializers.Serializer):
    """POST /api/artifacts/{artifact_id}/description/ — 맞춤 설명 + 연결 유물 생성"""
    session_id = serializers.IntegerField()
