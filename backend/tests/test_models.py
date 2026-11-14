from __future__ import annotations

from collections import defaultdict

from app.ai.live_features import build_live_features
from app.ai.neural_agent import NeuralAgent
from app.config import Settings
from app.database.database import Database
from app.database.repositories import Repository
from app.services.simulation_clock import SimulationEngine
from tools.experiment import build_feature_rows


def make_engine(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "simulation.db"),
        replay_sessions=2,
        bars_per_session=30,
        agent_decision_every=5,
        autostart=False,
        data_source="synthetic",
        seed=4242,
        model_dir=str(tmp_path / "models"),
        ml_autotrain=False,
    )
    db = Database(settings.db_path)
    repo = Repository(db)
    engine = SimulationEngine(repo, settings)
    engine.initialize()
    return engine, db


def test_live_features_match_training_features(tmp_path):
    engine, db = make_engine(tmp_path)
    try:
        repo = engine.repo
        bar_rows = repo.all_bars()
        total_bars = max(int(row["bar_index"]) for row in bar_rows) + 1
        # Synthetic data has several intraday bars per session; use the bar index
        # as the offset, which is also what the live context uses.
        dates = [f"session-{index}" for index in range(total_bars)]
        bars = defaultdict(dict)
        for row in bar_rows:
            bars[row["ticker"]][int(row["bar_index"])] = row
        news_by_offset = [defaultdict(lambda: (0.0, 0)) for _ in dates]
        for item in repo.all_news():
            offset = int(item["bar_index"])
            if not 0 <= offset < len(dates):
                continue
            key = item["ticker"] or "__MARKET__"
            score, count = news_by_offset[offset][key]
            news_by_offset[offset][key] = (
                score + float(item["sentiment"]),
                count + 1,
            )
        rows = build_feature_rows(
            dates=dates,
            bars=bars,
            news_by_offset=news_by_offset,
            tickers=engine.settings.stock_universe,
        )
        last = len(dates) - 1
        timeline = repo.timeline()
        context = engine.competition._context(
            bar_index=last,
            sim_time=timeline[last]["ts"],
            prices=repo.prices_at(last),
        )
        live = build_live_features(context)
        training = {(row.ticker, row.offset): row for row in rows}
        assert live
        for ticker, features in live.items():
            reference = training[(ticker, last)]
            assert len(features) == 26
            for observed, expected in zip(features, reference.features):
                assert abs(observed - expected) < 1e-9
    finally:
        engine.shutdown()
        db.close()


def test_neural_agent_maps_predictions_to_cross_sectional_percentiles(tmp_path):
    engine, db = make_engine(tmp_path)
    try:
        neural = next(
            agent for agent in engine.competition.agents if agent.model_type == "neural"
        )
        engine.models.score_context = lambda context: {
            "AAPL": -9.0,
            "MSFT": 0.0,
            "NVDA": 9.0,
        }
        timeline = engine.repo.timeline()
        last = len(timeline) - 1
        context = engine.competition._context(
            bar_index=last,
            sim_time=timeline[last]["ts"],
            prices=engine.repo.prices_at(last),
        )
        signals = {signal.ticker: signal.score for signal in neural.evaluate(
            context, engine.repo.load_state(neural.portfolio_id)
        )}
        assert signals == {"AAPL": -1.0, "MSFT": 0.0, "NVDA": 1.0}
    finally:
        engine.shutdown()
        db.close()
