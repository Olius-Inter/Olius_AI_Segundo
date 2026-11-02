"""Lê corpos em blocos com limite real, inclusive sem Content-Length."""
import asyncio
from starlette.responses import JSONResponse
from app.limits import MAX_BODY_BYTES


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app
        self.active = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if self.active >= 32:
            return await JSONResponse({"detail": "Serviço ocupado."}, 503)(scope, receive, send)
        self.active += 1
        started = False
        async def guarded_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                if scope.get("path", "").startswith(("/api/", "/sessions/")):
                    message = {**message, "headers": [
                        (k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"
                    ] + [(b"cache-control", b"no-store")]}
            await send(message)
        try:
            async with asyncio.timeout(90):
                await self._http(scope, receive, guarded_send)
        except TimeoutError:
            if not started:
                await JSONResponse({"detail": "Tempo máximo da requisição excedido."}, 504)(scope, receive, guarded_send)
        finally:
            self.active -= 1

    async def _http(self, scope, receive, send):
        body = bytearray()
        try:
            async with asyncio.timeout(10):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > MAX_BODY_BYTES:
                        return await JSONResponse({"detail": "Corpo da requisição excede o limite."}, 413)(scope, receive, send)
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await JSONResponse({"detail": "Tempo de envio excedido."}, 408)(scope, receive, send)
        consumed = False
        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()
        await self.app(scope, replay, send)
