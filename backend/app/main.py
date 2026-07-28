"""
InfoPulse — FastAPI Application Entry Point
=============================================
Start with: uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.core.database import Base, close_db, init_db
from app.core.errors import setup_error_handlers
from app.core.redis import close_redis, init_redis
from app.middleware.cors import setup_cors
from app.services.crawler.browser_manager import BrowserManager

# Ensure all models are imported before table creation
import app.models  # noqa: F401

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # --- Startup ---
    print("[InfoPulse] Starting up...")
    await init_db()
    print("[InfoPulse] Database connected")

    try:
        await init_redis()
        print("[InfoPulse] Redis connected")
    except Exception as e:
        print(f"[InfoPulse] Redis unavailable (non-fatal): {e}")

    print(f"[InfoPulse] Demo mode: {settings.DEMO_MODE}")
    print(f"[InfoPulse] Crawler enabled: {settings.CRAWLER_ENABLED}")
    print("[InfoPulse] Ready to serve requests")

    yield

    # --- Shutdown ---
    print("[InfoPulse] Shutting down...")
    await BrowserManager().close()
    await close_redis()
    await close_db()
    print("[InfoPulse] Goodbye")


app = FastAPI(
    title="InfoPulse API",
    description="AI-powered public opinion insight platform",
    version="1.0.0",
    lifespan=lifespan,
)

# --- Middleware ---
setup_cors(app)
setup_error_handlers(app)

# --- Routes ---
from app.api import auth, contents, history, hot_search, insights, mouthpiece, search, sources, timeline  # noqa: E402

app.include_router(auth.router)
app.include_router(insights.router)
app.include_router(mouthpiece.router)
app.include_router(timeline.router)
app.include_router(hot_search.router)
app.include_router(history.router)
app.include_router(sources.router)
app.include_router(search.router)
app.include_router(contents.router)


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint — used by monitoring and frontend."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "demo_mode": settings.DEMO_MODE,
        "crawler_enabled": settings.CRAWLER_ENABLED,
        "llm_configured": bool(settings.LLM_API_KEY and "your-api-key" not in settings.LLM_API_KEY),
        "modules": ["insights", "mouthpiece", "timeline", "hot_search", "history", "sources", "search", "events"],
    }
