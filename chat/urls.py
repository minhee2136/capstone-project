from django.urls import path
from . import views

urlpatterns = [
    path('chat/<int:session_id>/messages/', views.ChatMessageView.as_view(), name='chat-messages'),
    path('recommendations/<int:rec_id>/feedback/', views.FeedbackView.as_view(), name='feedback'),
]