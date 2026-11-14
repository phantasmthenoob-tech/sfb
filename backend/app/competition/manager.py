"""Runs each agent's independent decision loop against the shared replay."""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone

from ..ai.base_agent import BaseAgent, MarketContext, OrderIntent
from ..ai.combined_agent import CombinedAgent
from ..ai.features import sentiment_scores
from ..ai.news_agent import NewsAgent
from ..ai.price_agent import PriceAgent
from ..config import Settings
from ..database.repositories import Repository
from ..trading.order_manager import OrderManager
from ..trading.risk_limits import OrderRejected

logger = logging.getLogger(__name__)

AGENT_CLASSES = {
    "price": PriceAgent,
    "news": NewsAgent,
    "combined": CombinedAgent,
}


class CompetitionManager:
    def __init__(self, repo: Repository, settings: Settings, order_manager: OrderManager) -> None:
        self.repo = repo
        self.settings = settings
        self.order_manager = order_manager
        self.agents: list[BaseAgent] = []
        self._history: dict[str, deque] = {}
        self._history_cursor = -1

    def load_agents(self) -> list[BaseAgent]:
        agents: list[BaseAgent] = []
        for agent_row in self.repo.list_agents():
            portfolio = self.repo.get_portfolio_by_agent(agent_row["id"])
            if not portfolio:
                continue
            agent_class = AGENT_CLASSES.get(agent_row["model_type"])
            if agent_class is None:
                logger.warning("No strategy registered for model type %s", agent_row["model_type"])
                continue
            agents.append(
                agent_class(
                    agent_id=agent_row["id"],
                    name=agent_row["name"],
                    portfolio_id=portfolio["id"],
                    repo=self.repo,
                    settings=self.settings,
                )
            )
        self.agents = agents
        return agents

    def reset_history(self) -> None:
        """Force the next context to reload, after reset or a live-bar update."""
        self._history.clear()
        self._history_cursor = -1

    def _bars_for_context(self, bar_index: int) -> dict[str, list[dict]]:
        """Keep one rolling 120-bar window per stock instead of 120 queries/bar."""
        tickers = self.settings.stock_universe
        if bar_index == self._history_cursor:
            return {
                ticker: list(self._history.get(ticker, ()))
                for ticker in tickers
            }
        if bar_index == self._history_cursor + 1 and self._history:
            for row in self.repo.bars_at(bar_index):
                ticker = row["ticker"]
                if ticker in self._history:
                    self._history[ticker].append(row)
        else:
            self.reset_history()
            self._history = {
                ticker: deque(
                    self.repo.bars_for(ticker, up_to=bar_index, limit=120),
                    maxlen=120,
                )
                for ticker in tickers
            }
        self._history_cursor = bar_index
        return {
            ticker: list(self._history.get(ticker, ()))
            for ticker in tickers
        }

    def _context(
        self, *, bar_index: int, sim_time: str, prices: dict[str, float]
    ) -> MarketContext:
        bars = self._bars_for_context(bar_index)
        news = list(reversed(self.repo.news_up_to(bar_index, limit=4000)))
        sentiments = sentiment_scores(
            news, self.settings.stock_universe, max(0, bar_index - 5)
        )
        return MarketContext(
            sim_time=sim_time,
            bar_index=bar_index,
            prices=prices,
            bars=bars,
            news=news,
            sentiments=sentiments,
        )

    def run_forecasts(
        self, *, bar_index: int, sim_time: str, prices: dict[str, float]
    ) -> None:
        """Record fresh forecasts for every agent without submitting orders."""
        if not self.agents:
            self.load_agents()
        context = self._context(bar_index=bar_index, sim_time=sim_time, prices=prices)
        for agent in self.agents:
            agent.record_forecasts(context)

    def run_decisions(
        self, *, bar_index: int, sim_time: str, prices: dict[str, float]
    ) -> list[dict]:
        """Ask every agent for intents, then route them through the order manager."""
        if not self.agents:
            self.load_agents()
        context = self._context(bar_index=bar_index, sim_time=sim_time, prices=prices)
        submitted_at = datetime.now(timezone.utc).isoformat()
        submitted: list[dict] = []
        for agent in self.agents:
            intents: list[OrderIntent] = agent.step(context)
            for intent in intents:
                try:
                    order = self.order_manager.submit(
                        portfolio_id=agent.portfolio_id,
                        ticker=intent.ticker,
                        side=intent.side,
                        quantity=intent.quantity,
                        source=f"ai:{agent.model_type}",
                        sim_time=sim_time,
                        submitted_at=submitted_at,
                    )
                    submitted.append({"agent": agent.name, **order})
                except OrderRejected as exc:
                    logger.info("%s order rejected up front: %s", agent.name, exc.detail)
        return submitted

    @staticmethod
    def agent_view(agent: dict, portfolio_view: dict, latest_prediction: dict | None) -> dict:
        return {
            "id": agent["id"],
            "name": agent["name"],
            "model_type": agent["model_type"],
            "description": agent["description"],
            "portfolio": portfolio_view,
            "latest_prediction": latest_prediction,
        }
