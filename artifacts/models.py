from django.db import models
import numpy as np


class Artifact(models.Model):
    cleveland_id = models.IntegerField(unique=True)
    title = models.TextField()
    type = models.TextField(blank=True)
    department = models.TextField(blank=True)
    collection = models.TextField(blank=True)
    technique = models.TextField(blank=True)
    culture = models.JSONField(default=list, blank=True)
    creation_date_earliest = models.IntegerField(null=True, blank=True)
    creation_date_latest = models.IntegerField(null=True, blank=True)
    current_location = models.TextField(blank=True)
    image_url = models.TextField(blank=True)
    description = models.TextField(blank=True)
    embedding_text = models.TextField(blank=True)
    embedding_vector = models.JSONField(null=True, blank=True)
    accession_number = models.TextField(blank=True)
    tombstone = models.TextField(blank=True)
    measurements = models.TextField(blank=True)
    share_license_status = models.CharField(max_length=20, default='CC0')
    is_active = models.BooleanField(default=False)
    updated_at = models.CharField(max_length=50, blank=True)
    keyword = models.TextField(blank=True)

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