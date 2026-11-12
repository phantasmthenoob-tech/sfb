"""AI agent endpoints: portfolios, predictions, and the leaderboard teams."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..competition.leaderboard import build_portfolio_view
from ..competition.manager import CompetitionManager
from ..database.repositories import Repository
from ..services.simulation_clock import SimulationEngine
from .deps import get_engine, get_repo

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
def list_agents(
    engine: SimulationEngine = Depends(get_engine), repo: Repository = Depends(get_repo)
) -> dict:
    prices = {quote["ticker"]: quote["price"] for quote in engine.quotes_payload()}
    agents = []
    for agent in repo.list_agents():
        portfolio = repo.get_portfolio_by_agent(agent["id"])
        if not portfolio:
            continue
        predictions = repo.list_predictions(agent["id"], limit=1)
        view = build_portfolio_view(repo, portfolio, prices)
        agents.append(CompetitionManager.agent_view(agent, view, predictions[0] if predictions else None))
    return {"agents": agents, "simulation": engine.status_payload()}


@router.get("/{agent_id}")
def get_agent(
    agent_id: int,
    engine: SimulationEngine = Depends(get_engine),
    repo: Repository = Depends(get_repo),
) -> dict:
    agent = repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Unknown agent")
    portfolio = repo.get_portfolio_by_agent(agent_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Agent portfolio missing")
    prices = {quote["ticker"]: quote["price"] for quote in engine.quotes_payload()}
    predictions = repo.list_predictions(agent_id, limit=1)
    return CompetitionManager.agent_view(
        agent,
        build_portfolio_view(repo, portfolio, prices),
        predictions[0] if predictions else None,
    )


@router.get("/{agent_id}/portfolio")
def agent_portfolio(
    agent_id: int,
    engine: SimulationEngine = Depends(get_engine),
    repo: Repository = Depends(get_repo),
) -> dict:
    portfolio = repo.get_portfolio_by_agent(agent_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Agent portfolio missing")
    prices = {quote["ticker"]: quote["price"] for quote in engine.quotes_payload()}
    return build_portfolio_view(repo, portfolio, prices, include_history=True)


@router.get("/{agent_id}/predictions")
def agent_predictions(
    agent_id: int,
    limit: int = Query(default=25, ge=1, le=100),
    repo: Repository = Depends(get_repo),
) -> dict:
    if not repo.get_agent(agent_id):
        raise HTTPException(status_code=404, detail="Unknown agent")
    return {"predictions": repo.list_predictions(agent_id, limit=limit)}
