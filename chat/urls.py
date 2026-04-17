from django.urls import path
from . import views

urlpatterns = [
    path('chats/', views.ChatCreateView.as_view(), name='chat-create'),
    path('chats/<int:chat_id>/recommendations/', views.ChatRecommendationsView.as_view(), name='chat-recommendations'),
    path('chats/<int:chat_id>/feedback/', views.ChatFeedbackView.as_view(), name='chat-feedback'),
    path('chats/<int:chat_id>/next-recommendation/', views.ChatNextRecommendationView.as_view(), name='chat-next-recommendation'),
    path('chats/<int:chat_id>/reason/', views.ChatReasonView.as_view(), name='chat-reason'),
    path('chats/<int:chat_id>/similar/', views.ChatSimilarView.as_view(), name='chat-similar'),
    path('chats/<int:chat_id>/shortest/', views.ChatShortestView.as_view(), name='chat-shortest'),
    path('chats/<int:chat_id>/summary/', views.ChatSummaryView.as_view(), name='chat-summary'),
    path('chats/<int:chat_id>/route/', views.ChatRouteView.as_view(), name='chat-route'),
    path('chats/<int:chat_id>/history/', views.ChatHistoryView.as_view(), name='chat-history'),
    path('chats/<int:chat_id>/share/', views.ChatShareView.as_view(), name='chat-share'),
    path('chats/<int:chat_id>/talk/', views.ChatTalkView.as_view(), name='chat-talk'),
    path('chats/<int:chat_id>/visit/', views.ChatVisitView.as_view(), name='chat-visit'),
]
