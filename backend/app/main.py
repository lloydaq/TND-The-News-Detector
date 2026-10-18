import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import Receive, Scope, Send

from app.routes.analysis import router as analysis_router

app = FastAPI(title="TND Backend")
logging.getLogger("httpx").setLevel(logging.WARNING)
MAX_REQUEST_BODY_BYTES = 512_000


async def _send_body_limit_response(send: Send) -> None:
    body = b'{"detail":"Request body is too large."}'
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class RequestBodyLimitMiddleware:
    """Reject oversized HTTP bodies, including chunked requests."""

    def __init__(self, app, max_bytes: int = MAX_REQUEST_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = next(
            (
                value
                for name, value in scope.get("headers", [])
                if name.lower() == b"content-length"
            ),
            None,
        )
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    await _send_body_limit_response(send)
                    return
            except ValueError:
                pass

        total = 0
        exhausted = False

        async def limited_receive():
            nonlocal total, exhausted
            message = await receive()
            if message.get("type") == "http.request" and not exhausted:
                chunk = message.get("body", b"")
                total += len(chunk)
                if total > self.max_bytes:
                    exhausted = True
                    raise _RequestBodyTooLarge
                if not message.get("more_body", False):
                    exhausted = True
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestBodyTooLarge:
            await _send_body_limit_response(send)


class _RequestBodyTooLarge(Exception):
    pass

default_origins = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
env_origins = os.getenv("ALLOWED_ORIGINS", "")
if env_origins:
    for origin in env_origins.split(","):
        clean_origin = origin.strip()
        if clean_origin and clean_origin not in default_origins:
            default_origins.append(clean_origin)

# Allow the local frontend to communicate with the backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=default_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.add_middleware(RequestBodyLimitMiddleware)



@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "TND Backend",
    }


app.include_router(analysis_router, prefix="/api")
