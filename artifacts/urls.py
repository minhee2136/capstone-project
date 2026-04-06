from django.urls import path
from . import views

urlpatterns = [
    path('artifacts/<int:artifact_id>/', views.ArtifactDetailView.as_view(), name='artifact-detail'),
    path('artifacts/<int:artifact_id>/description/', views.ArtifactDescriptionView.as_view(), name='artifact-description'),
]
