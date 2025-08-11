from django.urls import path
from . import views

urlpatterns = [
    path('', views.ai_chat, name='chat'),
]