
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

django_asgi_app = get_asgi_application()

# Import the JWT middleware here after above line (asgi application is ready. The library includes user model and middleware)
from backend.auth_azure import AzureJWTMiddleware
import backend.routing # routing.py contains consumer which imports models, so must be placed after get_asgi_application   



application = ProtocolTypeRouter({
    "http": django_asgi_app,
    # Define the WebSocket protocol
    "websocket": AzureJWTMiddleware(
        URLRouter(
            backend.routing.websocket_urlpatterns  # Use your app's WebSocket routing
        )
    ),
})