import os
from django.core.asgi import get_asgi_application

# Set DJANGO_SETTINGS_MODULE FIRST before any other imports
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Initialize Django ASGI application early to configure settings
django_asgi_app = get_asgi_application()

# Now safely import other dependencies that need Django to be configured
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from chat.middleware import JWTAuthMiddleware
import chat.routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddleware(
            URLRouter(chat.routing.websocket_urlpatterns)
        )
    ),
})