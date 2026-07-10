"""
InfoPulse — CORS Middleware
============================
Configure Cross-Origin Resource Sharing for the FastAPI app.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def setup_cors(app: FastAPI) -> None:
    """Register CORS middleware with allowed origins."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",            # Vite dev server
            "http://localhost:4173",            # Vite preview
            "https://infopulse.vercel.app",     # Demo frontend (Vercel)
            # Add your custom domain here if you have one
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
