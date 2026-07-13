"""Optional application-wide bearer authentication.

Development remains zero-config.  Authentication becomes mandatory when a
token is configured, and production refuses to start without one.
"""
from __future__ import annotations

import secrets

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import Settings

PUBLIC_API_PATHS = frozenset({"/api/health"})


def _presented_bearer(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def token_is_valid(request: Request, expected_token: str) -> bool:
    presented = _presented_bearer(request)
    if presented is None:
        return False
    # compare_digest prevents a character-by-character timing oracle.
    return secrets.compare_digest(
        presented.encode("utf-8"), expected_token.encode("utf-8")
    )


def install_auth_middleware(app, settings: Settings) -> None:
    if not settings.auth_required():
        return

    @app.middleware("http")
    async def require_api_bearer(request: Request, call_next):
        # Browser CORS preflights do not carry the application bearer token.
        # CORSMiddleware still validates the requested origin/method/headers.
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path.rstrip("/") or "/"
        protected = (
            path.startswith("/api/")
            or path == "/api"
            or path in {"/", "/docs", "/redoc", "/openapi.json"}
        )
        if protected and path not in PUBLIC_API_PATHS:
            if not token_is_valid(request, settings.helixforge_api_token):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "invalid or missing bearer token"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
        return await call_next(request)
