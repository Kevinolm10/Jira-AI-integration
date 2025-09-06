from django.urls import path
from . import views

urlpatterns = [
    path('', views.ai_chat, name='chat'),
    path('chat/<str:session_id>/', views.ai_chat, name='ai_chat_session'),
    path('api/new-chat/', views.new_chat, name='new_chat'),
    path('api/delete-chat/<str:session_id>/', views.delete_chat, name='delete_chat'),
    path('api/rename-chat/<str:session_id>/', views.rename_chat, name='rename_chat'),
    path('api/chat-sessions/', views.get_chat_sessions, name='get_chat_sessions'),
]