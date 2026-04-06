from django.urls import path
from . import views

urlpatterns = [
    path('sessions/', views.SessionView.as_view(), name='session-create'),
]