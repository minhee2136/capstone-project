from rest_framework import serializers
from .models import ViewHistory


class ViewHistoryCreateSerializer(serializers.Serializer):
    artifact_id = serializers.IntegerField()


class ViewHistorySerializer(serializers.ModelSerializer):
    artifact_id = serializers.IntegerField(source='artifact.cleveland_id')
    title = serializers.CharField(source='artifact.title')
    image_url = serializers.CharField(source='artifact.image_url')

    class Meta:
        model = ViewHistory
        fields = ['id', 'artifact_id', 'title', 'image_url', 'visited_at']
