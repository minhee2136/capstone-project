from django.urls import path
from .views import RecommendPathView

urlpatterns = [
    path('path/', RecommendPathView.as_view(), name='recommend-path'),
]
