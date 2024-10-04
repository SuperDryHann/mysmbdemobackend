from django.urls import path

from . import views

app_name = "chat"
urlpatterns = [
    path('chat/', views.chat, name='chat'),
    path('chat_history/', views.ChatHistoryViewSet.as_view({'get': 'list'}), name='chat_history'),
    path('chat_history_client/', views.ChatHistoryClientViewSet.as_view({'get': 'list'}), name='chat_history_client'),
]