from __future__ import annotations

from dataclasses import replace

from app.services.simulation_clock import SimulationEngine


class FakeModels:
    def __init__(self, ready=False, trained_through_bar=None):
        self.calls = []
        self._status = {"ready": ready, "trained_through_bar": trained_through_bar}

    def status(self):
        return dict(self._status)

    def start_training(self, up_to_bar=None):
        self.calls.append(up_to_bar)
        return dict(self._status)


def make_engine(settings, repo, **overrides):
    engine_settings = replace(
        settings, data_source="yahoo", ml_autotrain=True, ml_retrain_bars=60, **overrides
    )
    engine = SimulationEngine(repo, engine_settings)
    engine.models = FakeModels()
    return engine


def test_autotrain_starts_once_history_is_available(settings, repo):
    engine = make_engine(settings, repo)
    engine.cursor = 59
    engine._maybe_autotrain()
    assert engine.models.calls == []
    engine.cursor = 60
    engine._maybe_autotrain()
    assert engine.models.calls == [60]


def test_autotrain_retrains_after_retrain_interval(settings, repo):
    engine = make_engine(settings, repo)
    engine.models = FakeModels(ready=True, trained_through_bar=100)
    engine.cursor = 150
    engine._maybe_autotrain()
    assert engine.models.calls == []
    engine.cursor = 160
    engine._maybe_autotrain()
    assert engine.models.calls == [160]
