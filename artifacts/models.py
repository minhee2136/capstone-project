from django.db import models

class Artifact(models.Model):
    # Cleveland API 기본 필드
    cleveland_id = models.IntegerField(unique=True)
    accession_number = models.CharField(max_length=50, blank=True)
    title = models.CharField(max_length=500)
    tombstone = models.TextField(blank=True)
    
    # 시대/제작 정보
    creation_date = models.CharField(max_length=100, blank=True)
    creation_date_earliest = models.IntegerField(null=True, blank=True)
    creation_date_latest = models.IntegerField(null=True, blank=True)
    
    # 분류
    department = models.CharField(max_length=200, blank=True)
    collection = models.CharField(max_length=200, blank=True)
    type = models.CharField(max_length=100, blank=True)
    technique = models.CharField(max_length=200, blank=True)
    culture = models.JSONField(default=list, blank=True)
    
    # 위치
    current_location = models.CharField(max_length=200, blank=True)
    
    # 이미지
    image_url = models.URLField(max_length=500, blank=True)
    image_url_full = models.URLField(max_length=500, blank=True)
    
    # 설명
    description = models.TextField(blank=True)
    did_you_know = models.TextField(blank=True)
    measurements = models.CharField(max_length=300, blank=True)
    
    # 라이선스
    share_license_status = models.CharField(max_length=50, blank=True)
    
    # 임베딩 (벡터 추천용)
    embedding_text = models.TextField(blank=True)  # 임베딩에 쓸 텍스트 조합
    # 임베딩 벡터 저장 (JSON으로 저장)
    embedding_vector = models.JSONField(null=True, blank=True)
    
    # 메타
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.creation_date})"

    class Meta:
        ordering = ['cleveland_id']