from django.urls import path
from chat import consumers

websocket_urlpatterns = [
    path('chat/', consumers.Chat.as_asgi()),
]
