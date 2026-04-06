from django.urls import path, include
from . import views

urlpatterns = [
    path('users/', views.UserView.as_view(), name='user-create'),
    path('api/', include('sessions.urls'))
]