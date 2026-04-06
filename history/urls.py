from django.urls import path
from . import views

urlpatterns = [
    path('sessions/<int:session_id>/history/', views.ViewHistoryView.as_view(), name='view-history'),
]
