from django.urls import path
from . import views

urlpatterns = [
    path('chat/<int:session_id>/messages/', views.ChatMessageView.as_view(), name='chat-messages'),
    path('recommendations/<int:rec_id>/feedback/', views.FeedbackView.as_view(), name='feedback'),
    path('chats/', views.ChatCreateView.as_view(), name='chat-create'),
    path('chats/<int:chat_id>/recommendations/', views.ChatRecommendationsView.as_view(), name='chat-recommendations'),
    path('chats/<int:chat_id>/feedback/', views.ChatFeedbackView.as_view(), name='chat-feedback'),
    path('chats/<int:chat_id>/next-recommendation/', views.ChatNextRecommendationView.as_view(), name='chat-next-recommendation'),
]