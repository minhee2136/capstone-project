from django.db import models


class ViewHistory(models.Model):
    session = models.ForeignKey(
        'sessions.Session',
        on_delete=models.CASCADE,
        related_name='view_histories',
    )
    artifact = models.ForeignKey(
        'artifacts.Artifact',
        on_delete=models.CASCADE,
        related_name='view_histories',
    )
    visited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'view_history'
        ordering = ['-visited_at']
