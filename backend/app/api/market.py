"""Market data endpoints, all restricted to the replay clock's cursor."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database.repositories import Repository
from ..market import data_provider
from ..market.data_processor import moving_average, quote_payload
from ..services.simulation_clock import SimulationEngine
from .deps import get_engine, get_repo

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/overview")
def market_overview(
    engine: SimulationEngine = Depends(get_engine),
    repo: Repository = Depends(get_repo),
) -> dict:
    status = engine.status_payload()
    quotes = engine.quotes_payload()
    prices = {quote["ticker"]: quote["price"] for quote in quotes}
    return {
        "simulation": status,
        "quotes": quotes,
        "indices": data_provider.index_levels(
            prices, engine.reference_prices(), engine.settings.universe
        ),
        "forecasts": engine.forecasts_payload(),
        "universe": list(engine.settings.universe),
        "data": engine.data_payload(),
        "data_note": "Simulated portfolios marked to real daily closes. Not investment advice.",
    }


@router.get("/quote/{ticker}")
def market_quote(
    ticker: str,
    engine: SimulationEngine = Depends(get_engine),
    repo: Repository = Depends(get_repo),
) -> dict:
    ticker = ticker.upper()
    if ticker not in engine.settings.universe:
        raise HTTPException(status_code=404, detail=f"Unknown ticker {ticker}")
    bar = repo.bar(ticker, engine.cursor)
    if not bar:
        raise HTTPException(status_code=404, detail=f"No replay price for {ticker}")
    previous_close = engine.reference_prices().get(ticker)
    payload = quote_payload(ticker, bar, previous_close)
    payload["sim_time"] = engine.timeline[engine.cursor]["ts"]
    return payload


@router.get("/history/{ticker}")
def market_history(
    ticker: str,
    limit: int = Query(default=200, ge=1, le=780),
    engine: SimulationEngine = Depends(get_engine),
    repo: Repository = Depends(get_repo),
) -> dict:
    ticker = ticker.upper()
    if ticker not in engine.settings.universe:
        raise HTTPException(status_code=404, detail=f"Unknown ticker {ticker}")
    bars = repo.bars_for(ticker, up_to=engine.cursor, limit=limit)
    closes = [bar["close"] for bar in bars]
    return {
        "ticker": ticker,
        "bars": bars,
        "sim_time": engine.timeline[engine.cursor]["ts"],
        "sma5": moving_average(closes, 5),
        "sma20": moving_average(closes, 20),
        "data": engine.data_payload(),
    }


@router.get("/news/{ticker}")
def market_news(
    ticker: str,
    limit: int = Query(default=30, ge=1, le=100),
    engine: SimulationEngine = Depends(get_engine),
    repo: Repository = Depends(get_repo),
) -> dict:
    ticker = ticker.upper()
    if ticker not in ("ALL", "MARKET") and ticker not in engine.settings.universe:
        raise HTTPException(status_code=404, detail=f"Unknown ticker {ticker}")
    requested = None if ticker in ("ALL", "MARKET") else ticker
    return {
        "ticker": ticker,
        "news": repo.news_up_to(engine.cursor, ticker=requested, limit=limit),
    }
