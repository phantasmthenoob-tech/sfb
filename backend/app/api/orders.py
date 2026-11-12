"""Manual paper-trading orders plus shared order/trade/prediction history."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..database.repositories import Repository
from ..services.simulation_clock import SimulationEngine
from ..trading.accounting import trade_fee
from ..trading.risk_limits import OrderRejected
from .deps import get_engine, get_repo

router = APIRouter(prefix="/api", tags=["orders"])


class OrderRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    side: str = Field(min_length=1, max_length=10)
    quantity: int = Field(gt=0, le=1_000_000)
    portfolio_id: int | None = None


@router.post("/orders", status_code=201)
def submit_order(
    payload: OrderRequest,
    engine: SimulationEngine = Depends(get_engine),
    repo: Repository = Depends(get_repo),
) -> dict:
    portfolio_id = payload.portfolio_id
    if portfolio_id is None:
        manual = repo.get_manual_portfolio()
        if not manual:
            raise HTTPException(status_code=404, detail="Manual portfolio not available")
        portfolio_id = manual["id"]
    else:
        portfolio = repo.get_portfolio(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Unknown portfolio")
        if portfolio["kind"] != "manual":
            raise HTTPException(
                status_code=400,
                detail="AI portfolios are managed by their strategies; manual orders use your portfolio",
            )

    current = engine.last_prices.get(payload.ticker.upper().strip())
    try:
        order = engine.order_manager.submit(
            portfolio_id=portfolio_id,
            ticker=payload.ticker,
            side=payload.side,
            quantity=payload.quantity,
            source="manual",
            sim_time=engine.timeline[engine.cursor]["ts"],
            submitted_at=datetime.now(timezone.utc).isoformat(),
        )
    except OrderRejected as exc:
        raise HTTPException(status_code=400, detail={"reason": exc.reason, "message": exc.detail}) from exc

    fill_note = (
        "Order queued. It fills on the next live quote."
        if engine.mode == "live"
        else "Order queued. Market orders fill at the next trading day's open price."
    )
    return {
        "order": order,
        "status": "PENDING",
        "message": fill_note,
        "indicative_price": current,
        "estimated_fee": trade_fee((current or 0) * payload.quantity, engine.settings.fee_bps),
        "simulation": engine.status_payload(),
    }


@router.get("/orders")
def list_orders(
    portfolio_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    repo: Repository = Depends(get_repo),
) -> dict:
    return {"orders": repo.list_orders(portfolio_id, limit=limit)}


@router.get("/trades")
def list_trades(
    portfolio_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    repo: Repository = Depends(get_repo),
) -> dict:
    return {"trades": repo.list_trades(portfolio_id, limit=limit)}


@router.get("/predictions")
def list_predictions(
    agent_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    repo: Repository = Depends(get_repo),
) -> dict:
    return {"predictions": repo.list_predictions(agent_id, limit=limit)}
