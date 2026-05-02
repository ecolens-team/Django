import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'EcoLens.settings')
django.setup()

from django.core.asgi import get_asgi_application # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator # noqa: E402
from channels.middleware import BaseMiddleware # noqa: E402
from channels.db import database_sync_to_async # noqa: E402
from channels.auth import AuthMiddlewareStack # noqa: E402
import users.routing # noqa: E402


class JWTCookieMiddleware(BaseMiddleware):

    async def __call__(self, scope, receive, send):
        scope["user"] = await self.get_user_from_cookie(scope)
        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user_from_cookie(self, scope):
        from django.contrib.auth.models import AnonymousUser
        from rest_framework_simplejwt.tokens import AccessToken
        from users.models import User

        headers = dict(scope.get("headers", []))
        cookie_header = headers.get(b"cookie", b"").decode()

        token_key = None
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith("jwt-auth="):
                token_key = part.split("=", 1)[1]
                break

        if not token_key:
            return AnonymousUser()

        try:
            token = AccessToken(token_key)
            return User.objects.get(id=token["user_id"])
        except Exception as e:
            print(f"WS JWT Error: {e}")
            return AnonymousUser()


application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            JWTCookieMiddleware(
                URLRouter(
                    users.routing.websocket_urlpatterns
                )
            )
        )
    ),
})