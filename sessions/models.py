from django.db import models
from django.contrib.postgres.fields import ArrayField
from users.models import User


class Session(models.Model):

    class KnowledgeLevel(models.TextChoices):
        BEGINNER = 'beginner', '초급'
        INTERMEDIATE = 'intermediate', '중급'
        ADVANCED = 'advanced', '고급'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions',
        verbose_name='사용자',
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
    history_embedding = models.JSONField(null=True, blank=True, verbose_name='히스토리 임베딩 벡터')
    current_location = models.CharField(max_length=100, blank=True, verbose_name='현재 위치(전시실)')
    is_active = models.BooleanField(default=True, verbose_name='활성 여부')
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sessions'
        verbose_name = '세션'
        verbose_name_plural = '세션 목록'

    def __str__(self):
        return f"Session {self.id} - {self.user.nickname}"