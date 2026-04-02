from django.db import models

class Artifact(models.Model):
    cleveland_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=500)
    type = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=200, blank=True)
    collection = models.CharField(max_length=200, blank=True)
    technique = models.CharField(max_length=200, blank=True)
    culture = models.JSONField(default=list, blank=True)
    creation_date = models.CharField(max_length=100, blank=True)
    creation_date_earliest = models.IntegerField(null=True, blank=True)
    creation_date_latest = models.IntegerField(null=True, blank=True)
    current_location = models.CharField(max_length=200, blank=True)
    image_url = models.URLField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    did_you_know = models.TextField(blank=True)
    # 추가
    artists_tags = models.JSONField(default=list, blank=True)
    series = models.CharField(max_length=500, blank=True)
    # 임베딩
    embedding_text = models.TextField(blank=True)
    embedding_vector = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.creation_date})"

    class Meta:
        ordering = ['cleveland_id']