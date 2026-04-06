from django.urls import path
from . import views

urlpatterns = [
    path('sessions/', views.SessionView.as_view(), name='session-create'),
    path('sessions/<int:session_id>/history-embedding', views.SessionHistoryEmbeddingView.as_view(), name='session-history-embedding'),
    path('sessions/<int:session_id>/candidates', views.SessionCandidatesView.as_view(), name='session-candidates'),
]