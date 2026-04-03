from django.urls import path
from .views import UserListView, UserDetailView

urlpatterns = [
    path('', UserListView.as_view()),
    path('<int:user_id>/', UserDetailView.as_view()),
]
