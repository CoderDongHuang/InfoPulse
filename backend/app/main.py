"""
InfoPulse — FastAPI Application Entry Point
=============================================
Start with: uvicorn app.main:app --reload --port 8000
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.core.database import Base, close_db, init_db
from app.core.errors import setup_error_handlers
from app.core.redis import close_redis, init_redis
from app.middleware.cors import setup_cors
from app.services.crawler.browser_manager import BrowserManager
from app.services.automation import scheduler_loop
from app.services.knowledge import knowledge_worker_loop
from app.services.orchestration import orchestration_worker_loop
from app.services.multimodal import media_worker_loop
from app.services.action_worker import action_operations_loop
from app.core.observability import setup_observability

# Ensure all models are imported before table creation
import app.models  # noqa: F401

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # --- Startup ---
    settings.assert_production_ready()
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
    scheduler_stop = asyncio.Event()
    run_embedded = settings.RUN_BACKGROUND_WORKERS_IN_API
    scheduler_task = asyncio.create_task(scheduler_loop(scheduler_stop)) if run_embedded and settings.TASK_SCHEDULER_ENABLED else None
    knowledge_stop = asyncio.Event()
    knowledge_task = asyncio.create_task(knowledge_worker_loop(knowledge_stop)) if run_embedded else None
    orchestration_stop = asyncio.Event()
    orchestration_task = asyncio.create_task(orchestration_worker_loop(orchestration_stop)) if run_embedded and settings.ORCHESTRATION_WORKER_ENABLED else None
    media_stop = asyncio.Event()
    media_task = asyncio.create_task(media_worker_loop(media_stop)) if run_embedded and settings.MEDIA_WORKER_ENABLED else None
    action_stop = asyncio.Event()
    action_task = asyncio.create_task(action_operations_loop(action_stop)) if run_embedded else None
    print("[InfoPulse] Ready to serve requests")

    yield

    # --- Shutdown ---
    print("[InfoPulse] Shutting down...")
    scheduler_stop.set()
    if scheduler_task:
        await scheduler_task
    knowledge_stop.set()
    if knowledge_task:
        await knowledge_task
    orchestration_stop.set()
    if orchestration_task:
        await orchestration_task
    media_stop.set()
    if media_task:
        await media_task
    action_stop.set()
    if action_task:
        await action_task
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
setup_observability(app)

# --- Routes ---
from app.api import action_loop, adaptive_intelligence, agent, analyses, auth, automation, autonomous_enterprise, commercialization, contents, enterprise, events, global_coordination, global_intelligence, graph, history, hot_search, insights, knowledge, mouthpiece, multimodal, operations, operations_center, orchestration, personalization, planetary_resilience, platform, provable_autonomy, reports, search, sources, stage3, stage10, timeline, trusted_ecosystem  # noqa: E402

app.include_router(auth.router)
app.include_router(insights.router)
app.include_router(mouthpiece.router)
app.include_router(timeline.router)
app.include_router(hot_search.router)
app.include_router(history.router)
app.include_router(sources.router)
app.include_router(search.router)
app.include_router(contents.router)
app.include_router(events.router)
app.include_router(personalization.router)
app.include_router(stage3.router)
app.include_router(analyses.router)
app.include_router(agent.router)
app.include_router(reports.router)
app.include_router(automation.router)
app.include_router(knowledge.router)
app.include_router(graph.router)
app.include_router(stage10.router)
app.include_router(operations.router)
app.include_router(operations_center.router)
app.include_router(enterprise.router)
app.include_router(enterprise.scim_router)
app.include_router(platform.router)
app.include_router(orchestration.router)
app.include_router(multimodal.router)
app.include_router(global_intelligence.router)
app.include_router(action_loop.router)
app.include_router(commercialization.router)
app.include_router(autonomous_enterprise.router)
app.include_router(trusted_ecosystem.router)
app.include_router(global_coordination.router)
app.include_router(adaptive_intelligence.router)
app.include_router(provable_autonomy.router)
app.include_router(planetary_resilience.router)


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
