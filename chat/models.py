from django.db import models
from sessions.models import Session


class Message(models.Model):

    class Role(models.TextChoices):
        USER = 'user', '사용자'
        ASSISTANT = 'assistant', '큐레이터'

    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='세션',
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        verbose_name='역할',
    )
    content = models.TextField(verbose_name='메시지 내용')
    artifact_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='추천 유물 ID',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'messages'
        verbose_name = '메시지'
        verbose_name_plural = '메시지 목록'
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.role}] Session {self.session.id} - {self.content[:30]}"


class Feedback(models.Model):

    class FeedbackType(models.TextChoices):
        LIKE = 'like', '흥미로워요'
        DISLIKE = 'dislike', '별로예요'
        WHY = 'why', '왜 이거예요?'
        SIMILAR = 'similar', '비슷한 작품'
        SHORT_ROUTE = 'short_route', '짧은 경로'

    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='feedbacks',
        verbose_name='세션',
    )
    artifact_id = models.IntegerField(verbose_name='유물 ID')
    feedback_type = models.CharField(
        max_length=20,
        choices=FeedbackType.choices,
        verbose_name='피드백 유형',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'feedbacks'
        verbose_name = '피드백'
        verbose_name_plural = '피드백 목록'

    def __str__(self):
        return f"Feedback {self.id} - {self.feedback_type}"