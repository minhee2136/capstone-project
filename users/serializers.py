from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'nickname', 'gender', 'birth_year', 'created_at']
        read_only_fields = ['id', 'created_at']
