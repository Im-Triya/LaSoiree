import django
django.setup()

import jwt
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
User = get_user_model()


@database_sync_to_async
def get_user(validated_token):
    try:
        user_id = validated_token.get("user_id") or validated_token.get("user")
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()



class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        # Extract token from query string
        query_string = scope["query_string"].decode()
        token = None

        if "token=" in query_string:
            token = query_string.split("token=")[-1].split("&")[0]

        if token:
            try:
                validated_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                scope["user"] = await get_user(validated_token)
            except jwt.ExpiredSignatureError:
                scope["user"] = AnonymousUser()
            except jwt.InvalidTokenError:
                scope["user"] = AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
