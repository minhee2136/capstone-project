from django.urls import path
from . import views

urlpatterns = [
    path('artifacts/sync/', views.SyncArtifactsView.as_view(), name='artifacts-sync'),
    path('artifacts/<int:artifact_id>/', views.ArtifactDetailView.as_view(), name='artifact-detail'),
    path('artifacts/<int:artifact_id>/recent-artifact/', views.ArtifactRecentView.as_view(), name='artifact-recent'),
    path('artifacts/<int:artifact_id>/ai-description/', views.ArtifactAiDescriptionView.as_view(), name='artifact-ai-description'),
]
