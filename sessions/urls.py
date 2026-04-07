from django.urls import path
from . import views

urlpatterns = [
    path('sessions/', views.SessionView.as_view(), name='session-create'),
    path('sessions/<int:session_id>/', views.SessionDetailView.as_view(), name='session-detail'),
    path('sessions/<int:session_id>/end/', views.SessionEndView.as_view(), name='session-end'),
    path('sessions/<int:session_id>/location/', views.SessionLocationView.as_view(), name='session-location'),
    path('sessions/<int:session_id>/candidates', views.SessionCandidatesView.as_view(), name='session-candidates'),
    path('sessions/<int:session_id>/summary/', views.SessionSummaryView.as_view(), name='session-summary'),
    path('sessions/<int:session_id>/summary/next-topics/', views.SessionSummaryNextTopicsView.as_view(), name='session-summary-next-topics'),
    path('sessions/<int:session_id>/summary/share/', views.SessionSummaryShareView.as_view(), name='session-summary-share'),
]