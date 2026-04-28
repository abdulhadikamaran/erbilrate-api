"""
Application Entry Point
========================
Creates the FastAPI app, wires up database lifecycle,
starts the background scheduler, registers routes,
serves the frontend static files, and configures middleware.

Run with:
    uvicorn app.main:app --reload
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app import db
from app import cache
from app.api.routes import router as api_router
from app.api.admin import router as admin_router
from app.scheduler.jobs import start_scheduler
from app.scheduler.maintenance import cleanup_loop, history_cache_loop
from app.ws_manager import manager
from app.config import settings

# ── Paths ─────────────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# ── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Starting Erbil USD/IQD Rate API...")

    # Init PostgreSQL pool + schema
    await db.init_db()

    # Init Redis cache (non-fatal if Redis is unavailable)
    await cache.init_redis()

    scheduler_task = asyncio.create_task(start_scheduler())
    maintenance_task = asyncio.create_task(cleanup_loop())
    history_task = asyncio.create_task(history_cache_loop())
    pubsub_task = asyncio.create_task(cache.listen_for_rates(manager.broadcast))
    
    logger.info("Background tasks started (scheduler, maintenance, history_cache, pubsub)")
    logger.info("API is ready to serve requests")

    yield

    logger.info("Shutting down...")
    scheduler_task.cancel()
    maintenance_task.cancel()
    history_task.cancel()
    pubsub_task.cancel()
    
    try:
        await asyncio.gather(
            scheduler_task, maintenance_task, history_task, pubsub_task, return_exceptions=True
        )
    except asyncio.CancelledError:
        pass
        
    await cache.close_redis()
    await db.close_db()
    logger.info("Shutdown complete")


# ── App Creation ──────────────────────────────────────────────────────


app = FastAPI(
    title="Erbil USD/IQD Market Rate API",
    description=(
        "Provides the average USD to IQD market exchange rate for Erbil city, "
        "automatically extracted from a public Telegram channel."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None, # Disable default Swagger UI
    redoc_url=None,
)

# ── Request ID Middleware ─────────────────────────────────────────────────
# Injects a unique UUID into every request and response.
# All log entries for a single request carry the same X-Request-ID,
# making incident investigation trivial: grep logs by one UUID.
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── CORS Middleware ─────────────────────────────────────────────────
# Origins are loaded from ALLOWED_ORIGINS in .env.
# Default: local dev only. Production: set to your domain(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── API Routes ────────────────────────────────────────────────────────
app.include_router(api_router)
app.include_router(admin_router)
# ── Static Files ──────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Root → Frontend ──────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    """Serve the PWA frontend."""
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.get("/docs", include_in_schema=False)
async def custom_docs():
    """Serve the custom API Documentation page."""
    return FileResponse(str(STATIC_DIR / "docs.html"))
