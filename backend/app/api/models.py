"""Live model status and active-training controls."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..ai.model_registry import ModelRegistry
from ..services.simulation_clock import SimulationEngine
from .deps import get_engine, get_models

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("/status")
def status(models: ModelRegistry = Depends(get_models)) -> dict:
    return models.status()


@router.post("/train", status_code=202)
def train(
    models: ModelRegistry = Depends(get_models),
    engine: SimulationEngine = Depends(get_engine),
) -> dict:
    # Only history visible at the current replay cursor is allowed into the
    # model, so a replay cannot train on bars it has not reached yet.
    return models.start_training(engine.cursor)
