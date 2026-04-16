from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.core.config import get_settings
from app.core.redis import close_redis
from app.api.sessions import router as sessions_router
from app.api.memory import router as memory_router
from app.api.dashboard import router as dashboard_router
from app.api.events_stream import router as events_stream_router
from app.api.seed import router as seed_router
from app.api.auth import router as auth_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agent-black-box")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    yield
    await close_redis()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(sessions_router)
    app.include_router(memory_router)
    app.include_router(dashboard_router)
    app.include_router(events_stream_router)
    app.include_router(seed_router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "app": settings.app_name, "version": settings.app_version}

    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    EXPORT_PATH = PROJECT_ROOT / "agent-blackbox.tar.gz"

    @app.get("/api/export/status")
    async def export_status():
        if EXPORT_PATH.exists():
            size_mb = round(EXPORT_PATH.stat().st_size / (1024 * 1024), 1)
            return {"available": True, "size_mb": size_mb, "filename": EXPORT_PATH.name}
        return {"available": False, "size_mb": 0, "filename": None}

    @app.get("/api/export/download")
    async def export_download():
        if not EXPORT_PATH.exists():
            raise HTTPException(404, "Export not found. Run 'make export' first.")
        return FileResponse(
            path=str(EXPORT_PATH),
            media_type="application/gzip",
            filename="agent-blackbox.tar.gz",
        )

    return app


app = create_app()
