"""
Check the server-held bearer token before allowing protected API requests. Local development can
omit it; production configuration requires a suitably long secret.
"""

import os
import secrets
from fastapi import HTTPException, Request


def require_api_access(request: Request):
    """
    Enforce the configured bearer secret with constant-time comparison while permitting public
    liveness checks.
    """
    token = os.getenv("API_ACCESS_TOKEN", "")
    production = os.getenv("APP_ENV", "development") == "production"
    if production and len(token) < 32:
        raise HTTPException(
            503, "Production API_ACCESS_TOKEN must contain at least 32 characters."
        )
    if token and not secrets.compare_digest(
        request.headers.get("authorization", "").encode(), f"Bearer {token}".encode()
    ):
        raise HTTPException(
            401, "API authentication required.", headers={"WWW-Authenticate": "Bearer"}
        )
