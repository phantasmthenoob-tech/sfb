from __future__ import annotations

from app.config import default_data_dir, default_model_dir, resolve_db_path, resolve_storage_dir


def test_unwritable_storage_paths_fall_back(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not-a-directory")

    resolved_db = resolve_db_path(str(blocker / "simulation.db"))
    resolved_models = resolve_storage_dir(str(blocker / "models"), default_model_dir())

    assert resolved_db == str(default_data_dir() / "simulation.db")
    assert resolved_models == default_model_dir()
