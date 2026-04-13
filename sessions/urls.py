from django.urls import path
from . import views

urlpatterns = [
    path('sessions/', views.SessionView.as_view(), name='session-create'),
    path('sessions/<int:session_id>/', views.SessionDetailView.as_view(), name='session-detail'),
    path('sessions/<int:session_id>/history-summary/', views.SessionHistorySummaryView.as_view(), name='session-history-summary'),

]