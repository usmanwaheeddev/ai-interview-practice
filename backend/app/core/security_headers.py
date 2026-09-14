"""Baseline security response headers — Phase 6 hardening pass. This is a
JSON API (no server-rendered HTML beyond FastAPI's own error pages), so the
header set is deliberately small: the handful that matter regardless of
content type, not a browser-app CSP that has nothing to restrict here."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, hsts: bool) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._hsts = hsts

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(self), microphone=(self), geolocation=(), payment=()"
        )
        # camera/microphone stay same-origin-permitted — the interview room
        # legitimately needs them; everything else defaults closed.
        if self._hsts:
            # Only meaningful (and only sent) behind real TLS — see
            # settings.env check at the call site. Sending this over plain
            # HTTP in dev would just be a lie the browser ignores anyway,
            # but it's cleaner not to send it at all.
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response
