from django.db import models
import numpy as np


class Artifact(models.Model):
    cleveland_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=500)
    type = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=200, blank=True)
    collection = models.CharField(max_length=200, blank=True)
    technique = models.CharField(max_length=200, blank=True)
    culture = models.JSONField(default=list, blank=True)
    creation_date_earliest = models.IntegerField(null=True, blank=True)
    creation_date_latest = models.IntegerField(null=True, blank=True)
    current_location = models.CharField(max_length=200, blank=True)
    image_url = models.URLField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    did_you_know = models.TextField(blank=True)
    embedding_text = models.TextField(blank=True)
    embedding_vector = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.creation_date_earliest})"

    def get_embedding_vector(self):
        if self.embedding_vector is None:
            return None
        return np.array(self.embedding_vector, dtype=np.float32)

    class Meta:
        db_table = 'artifacts'
        ordering = ['cleveland_id']
        verbose_name = '유물'
        verbose_name_plural = '유물 목록'