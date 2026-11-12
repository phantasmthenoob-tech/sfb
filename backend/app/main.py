"""FastAPI application entry point for the market simulation backend."""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .api import agents, market, orders, portfolios, simulation
from .config import Settings
from .database.database import Database
from .database.repositories import Repository
from .services.event_manager import EventManager
from .services.simulation_clock import SimulationEngine

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def cors_origins() -> list[str]:
    """Parse CORS_ORIGINS into exact origins (comma-separated, no trailing slash)."""
    raw = os.environ.get("CORS_ORIGINS", "*")
    origins = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
    return origins or ["*"]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(settings.db_path)
        repo = Repository(db)
        events = EventManager()
        engine = SimulationEngine(repo, settings, events)
        engine.initialize()

        app.state.db = db
        app.state.repo = repo
        app.state.events = events
        app.state.engine = engine
        app.state.settings = settings

        engine._task = asyncio.create_task(engine.run_loop())
        logger.info(
            "Simulation ready: %s bars, status=%s, speed=%sx",
            engine.total_bars,
            engine.status,
            engine.speed,
        )
        try:
            yield
        finally:
            engine.shutdown()
            db.close()

    app = FastAPI(
        title="AI Market Simulator",
        description=(
            "Paper-trading replay where three independent AI portfolios and one manual "
            "portfolio compete on identical starting capital."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(market.router)
    app.include_router(agents.router)
    app.include_router(portfolios.router)
    app.include_router(orders.router)
    app.include_router(simulation.router)

    @app.get("/api/health", tags=["system"])
    def health() -> dict:
        engine = app.state.engine
        return {
            "status": "ok",
            "simulation": engine.status_payload(),
            "settings": settings.as_public_dict(),
        }

    @app.get("/", tags=["system"])
    def root() -> dict:
        return {
            "service": "ai-market-simulator",
            "docs": "/docs",
            "websocket": "/ws/market",
        }

    @app.websocket("/ws/market")
    async def market_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        engine: SimulationEngine = websocket.app.state.engine
        events: EventManager = websocket.app.state.events
        queue = events.subscribe()
        try:
            await websocket.send_json(engine.snapshot())
            while True:
                payload = await queue.get()
                await websocket.send_json(payload)
        except WebSocketDisconnect:
            pass
        except Exception:  # pragma: no cover - client vanished mid-send
            logger.debug("Websocket closed unexpectedly", exc_info=True)
        finally:
            events.unsubscribe(queue)

    return app


app = create_app()
