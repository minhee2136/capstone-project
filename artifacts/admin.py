from django.contrib import admin
from .models import Artifact


@admin.register(Artifact)
class ArtifactAdmin(admin.ModelAdmin):
    list_display = ['cleveland_id', 'title', 'type', 'department', 'creation_date_earliest']
    search_fields = ['title', 'department', 'type']
    list_filter = ['type', 'department']
