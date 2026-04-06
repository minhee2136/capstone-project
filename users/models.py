from django.db import models
from django.contrib.postgres.fields import ArrayField


class User(models.Model):

    class Gender(models.TextChoices):
        MALE = 'M', '남성'
        FEMALE = 'F', '여성'
        NONE = 'N', '선택 안 함'

    class KnowledgeLevel(models.TextChoices):
        BEGINNER = 'beginner', '초급'
        INTERMEDIATE = 'intermediate', '중급'
        ADVANCED = 'advanced', '고급'

    nickname = models.CharField(max_length=50, verbose_name='닉네임')
    gender = models.CharField(
        max_length=1,
        choices=Gender.choices,
        null=True,
        blank=True,
        verbose_name='성별',
    )
    birth_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='출생년도',
    )
    interest_tags = ArrayField(
        base_field=models.CharField(max_length=50),
        default=list,
        blank=True,
        verbose_name='관심 키워드',
    )
    knowledge_level = models.CharField(
        max_length=20,
        choices=KnowledgeLevel.choices,
        null=True,
        blank=True,
        verbose_name='지식 수준',
    )
    view_time_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='관람 희망 시간(분)',
    )
    interest_embedding = models.JSONField(
        null=True,
        blank=True,
        verbose_name='관심사 임베딩 벡터',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        verbose_name = '사용자'
        verbose_name_plural = '사용자 목록'

    def __str__(self):
        return f"{self.nickname} ({self.id})"