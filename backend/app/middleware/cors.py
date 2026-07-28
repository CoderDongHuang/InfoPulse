"""
InfoPulse — CORS Middleware
============================
Configure Cross-Origin Resource Sharing for the FastAPI app.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.config import get_settings


def setup_cors(app: FastAPI) -> None:
    """Register CORS middleware with allowed origins."""
    settings = get_settings()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
