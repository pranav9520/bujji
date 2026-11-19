"""Header-only ASGI middleware preserves the server's disconnect receive channel."""
from starlette.datastructures import MutableHeaders


class SecurityHeaders:
    def __init__(self,app):
        self.app=app

    async def __call__(self,scope,receive,send):
        async def with_headers(message):
            if message['type']=='http.response.start':
                headers=MutableHeaders(scope=message)
                headers.update({
                    'X-Content-Type-Options':'nosniff',
                    'Referrer-Policy':'no-referrer',
                    'Cache-Control':'no-store',
                    'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
                })
            await send(message)
        await self.app(scope,receive,with_headers)
