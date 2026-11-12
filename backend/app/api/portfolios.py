"""Leaderboard and per-portfolio views."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..competition.leaderboard import build_leaderboard, build_portfolio_view
from ..database.repositories import Repository
from ..services.simulation_clock import SimulationEngine
from .deps import get_engine, get_repo

router = APIRouter(prefix="/api", tags=["portfolios"])


def _prices(engine: SimulationEngine) -> dict[str, float]:
    quotes = engine.quotes_payload()
    return {quote["ticker"]: quote["price"] for quote in quotes} or engine.last_prices


@router.get("/leaderboard")
def leaderboard(
    engine: SimulationEngine = Depends(get_engine), repo: Repository = Depends(get_repo)
) -> dict:
    entries = build_leaderboard(repo, _prices(engine))
    return {
        "entries": entries,
        "simulation": engine.status_payload(),
        "ranking": "total_return_pct",
        "data_note": "Simulated results from synthetic replay data, not live trading.",
    }


@router.get("/portfolios")
def list_portfolios(
    engine: SimulationEngine = Depends(get_engine), repo: Repository = Depends(get_repo)
) -> dict:
    prices = _prices(engine)
    return {
        "portfolios": [
            build_portfolio_view(repo, portfolio, prices) for portfolio in repo.list_portfolios()
        ]
    }


@router.get("/portfolios/manual")
def manual_portfolio(
    engine: SimulationEngine = Depends(get_engine), repo: Repository = Depends(get_repo)
) -> dict:
    portfolio = repo.get_manual_portfolio()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Manual portfolio not available")
    return build_portfolio_view(repo, portfolio, _prices(engine), include_history=True)


@router.get("/portfolios/{portfolio_id}")
def portfolio_detail(
    portfolio_id: int,
    engine: SimulationEngine = Depends(get_engine),
    repo: Repository = Depends(get_repo),
) -> dict:
    portfolio = repo.get_portfolio(portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Unknown portfolio")
    return build_portfolio_view(repo, portfolio, _prices(engine), include_history=True)
