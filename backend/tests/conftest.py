from __future__ import annotations

from dataclasses import replace

import pytest

from app.config import Settings
from app.database.database import Database
from app.database.repositories import Repository


def make_settings(tmp_path, **overrides) -> Settings:
    base = Settings(
        db_path=str(tmp_path / "simulation.db"),
        replay_sessions=2,
        bars_per_session=12,
        agent_decision_every=50,
        autostart=False,
        data_source="synthetic",
        seed=4242,
    )
    return replace(base, **overrides) if overrides else base


@pytest.fixture
def settings(tmp_path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def repo(settings):
    db = Database(settings.db_path)
    repository = Repository(db)
    repository.seed_accounts(settings, "2026-09-14T09:30:00")
    yield repository
    db.close()
