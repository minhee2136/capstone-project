from django.urls import path
from . import views

urlpatterns = [
    path('artifacts/sync/', views.SyncArtifactsView.as_view(), name='artifacts-sync'),
    path('artifacts/<int:artifact_id>/', views.ArtifactDetailView.as_view(), name='artifact-detail'),
    path('artifacts/<int:artifact_id>/description/', views.ArtifactDescriptionView.as_view(), name='artifact-description'),
    path('artifacts/<int:artifact_id>/related/', views.ArtifactRelatedView.as_view(), name='artifact-related'),
]
