"""Replay clock controls."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..config import SPEED_OPTIONS
from ..services.simulation_clock import SimulationEngine
from .deps import get_engine

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


class SpeedRequest(BaseModel):
    speed: int


class ModeRequest(BaseModel):
    mode: str


class ReplayRangeRequest(BaseModel):
    preset: str


@router.get("/status")
def status(engine: SimulationEngine = Depends(get_engine)) -> dict:
    return engine.status_payload()


@router.post("/mode")
def set_mode(payload: ModeRequest, engine: SimulationEngine = Depends(get_engine)) -> dict:
    if payload.mode not in ("replay", "live"):
        raise HTTPException(status_code=400, detail="Mode must be 'replay' or 'live'")
    engine.switch_mode(payload.mode)
    return {"simulation": engine.status_payload(), "snapshot": engine.snapshot()}


@router.post("/start")
def start(engine: SimulationEngine = Depends(get_engine)) -> dict:
    engine.play()
    return {"simulation": engine.status_payload(), "snapshot": engine.snapshot()}


@router.post("/pause")
def pause(engine: SimulationEngine = Depends(get_engine)) -> dict:
    engine.pause()
    return {"simulation": engine.status_payload()}


@router.post("/reset")
def reset(engine: SimulationEngine = Depends(get_engine)) -> dict:
    engine.reset()
    return {"simulation": engine.status_payload(), "snapshot": engine.snapshot()}


@router.post("/range")
def set_replay_range(
    payload: ReplayRangeRequest, engine: SimulationEngine = Depends(get_engine)
) -> dict:
    try:
        engine.set_replay_range(payload.preset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"simulation": engine.status_payload(), "snapshot": engine.snapshot()}


@router.post("/speed")
def set_speed(payload: SpeedRequest, engine: SimulationEngine = Depends(get_engine)) -> dict:
    if payload.speed not in SPEED_OPTIONS:
        raise HTTPException(
            status_code=400, detail=f"Speed must be one of {list(SPEED_OPTIONS)}"
        )
    engine.set_speed(payload.speed)
    return {"simulation": engine.status_payload()}
