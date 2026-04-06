from django.urls import path, include
from . import views

urlpatterns = [
    path('users/', views.UserView.as_view(), name='user-create'),
    path('users/<int:user_id>/interest-embedding', views.UserInterestEmbeddingView.as_view(), name='user-interest-embedding'),
    path('api/', include('sessions.urls'))
]