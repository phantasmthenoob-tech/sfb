"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Request

from ..ai.model_registry import ModelRegistry
from ..database.repositories import Repository
from ..services.simulation_clock import SimulationEngine


def get_repo(request: Request) -> Repository:
    return request.app.state.repo


def get_engine(request: Request) -> SimulationEngine:
    return request.app.state.engine


def get_models(request: Request) -> ModelRegistry:
    return request.app.state.models
