"""Live neural-network model: walk-forward training, persistence and scoring."""
from __future__ import annotations

import logging
import os
import pickle
import statistics
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from ..config import Settings
from ..database.repositories import Repository
from .live_features import FEATURE_NAMES, build_live_features

logger = logging.getLogger(__name__)

MODEL_NAME = "neural"
ARTIFACT_NAME = "neural_network.pkl"


class ModelRegistry:
    """Owns the trained neural model and its active-training lifecycle.

    Training runs in a daemon thread so the simulation and HTTP API stay
    responsive. The previous model, if any, remains active until a new artifact
    has been written successfully.
    """

    def __init__(self, repo: Repository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings
        self.path = Path(settings.model_dir) / ARTIFACT_NAME
        self._lock = threading.RLock()
        self._bundle: dict | None = None
        self._thread: threading.Thread | None = None
        self._score_cache_key: tuple | None = None
        self._score_cache_values: dict[str, float] = {}
        self._status: dict = {
            "model": MODEL_NAME,
            "state": "untrained",
            "ready": False,
            "trained_at": None,
            "samples": 0,
            "features": len(FEATURE_NAMES),
            "train_samples": 0,
            "validation_samples": 0,
            "validation": {},
            "data_start": None,
            "data_end": None,
            "trained_through_bar": None,
            "error": None,
            "artifact": str(self.path),
        }
        self.load()

    # --------------------------------------------------------------- lifecycle
    def load(self) -> dict:
        with self._lock:
            if not self.path.exists():
                return self.status()
            try:
                with self.path.open("rb") as handle:
                    bundle = pickle.load(handle)
                if tuple(bundle.get("feature_names", ())) != FEATURE_NAMES:
                    raise ValueError("model feature layout does not match live features")
                self._bundle = bundle
                self._status.update(
                    {
                        "state": "ready",
                        "ready": True,
                        "trained_at": bundle.get("trained_at"),
                        "samples": int(bundle.get("samples") or 0),
                        "train_samples": int(bundle.get("train_samples") or 0),
                        "validation_samples": int(bundle.get("validation_samples") or 0),
                        "validation": bundle.get("validation") or {},
                        "data_start": bundle.get("data_start"),
                        "data_end": bundle.get("data_end"),
                        "trained_through_bar": bundle.get("train_end_bar"),
                        "error": None,
                    }
                )
            except Exception as exc:  # pragma: no cover - corrupt artifact path
                logger.warning("Could not load neural model: %s", exc)
                self._status.update({"state": "error", "ready": False, "error": str(exc)})
            return self.status()

    def status(self) -> dict:
        with self._lock:
            return dict(self._status)

    def start_training(self, up_to_bar: int | None = None) -> dict:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return dict(self._status)
            self._status.update({"state": "training", "error": None})
            self._thread = threading.Thread(
                target=self._train_guarded,
                args=(up_to_bar,),
                name="neural-model-training",
                daemon=True,
            )
            self._thread.start()
            return dict(self._status)

    def train_now(self, up_to_bar: int | None = None) -> dict:
        """Synchronous entry point used by tests and explicit maintenance."""
        self._train_guarded(up_to_bar)
        return self.status()

    def _train_guarded(self, up_to_bar: int | None = None) -> None:
        self._set_status(state="training", error=None)
        try:
            self._train(up_to_bar)
        except Exception as exc:  # pragma: no cover - data/environment dependent
            logger.exception("Neural model training failed")
            self._set_status(state="error", error=str(exc), ready=self._bundle is not None)
        finally:
            with self._lock:
                self._thread = None

    def _set_status(self, **values) -> None:
        with self._lock:
            self._status.update(values)

    # ------------------------------------------------------------------ training
    def _train(self, up_to_bar: int | None = None) -> None:
        import numpy as np
        from sklearn.neural_network import MLPRegressor

        from tools.experiment import HORIZON, build_feature_rows, training_rows

        started = time.time()
        all_bar_rows = self.repo.all_bars()
        if up_to_bar is None:
            up_to_bar = max((int(row["bar_index"]) for row in all_bar_rows), default=-1)
        bar_rows = [
            row for row in all_bar_rows if int(row["bar_index"]) <= int(up_to_bar)
        ]
        news_rows = [
            row for row in self.repo.all_news() if int(row["bar_index"]) <= int(up_to_bar)
        ]
        if not bar_rows:
            raise RuntimeError("No market bars have been recorded yet")
        total_bars = max(int(row["bar_index"]) for row in bar_rows) + 1
        # Bars are indexed by bar_index, not session date: synthetic fixtures can
        # contain several bars per date, while Yahoo daily data has one.
        offsets = [str(index) for index in range(total_bars)]
        session_dates = sorted({row["session_date"] for row in bar_rows})
        bars: dict[str, dict[int, dict]] = defaultdict(dict)
        for row in bar_rows:
            bars[row["ticker"]][int(row["bar_index"])] = row
        news_by_offset: list[dict[str, tuple[float, int]]] = [
            defaultdict(lambda: (0.0, 0)) for _ in offsets
        ]
        for item in news_rows:
            offset = int(item["bar_index"])
            if not 0 <= offset < len(offsets):
                continue
            key = item["ticker"] or "__MARKET__"
            score, count = news_by_offset[offset][key]
            news_by_offset[offset][key] = (
                score + float(item["sentiment"]),
                count + 1,
            )
        # Free the raw news dicts before materializing ~150k feature rows.
        del news_rows, all_bar_rows, bar_rows
        tickers = self.settings.stock_universe
        rows = build_feature_rows(
            dates=offsets,
            bars=bars,
            news_by_offset=news_by_offset,
            tickers=tickers,
            horizon=HORIZON,
        )
        del bars, news_by_offset
        labeled = [row for row in rows if row.label is not None]
        if len(labeled) < 2_000 or len(offsets) < 80:
            raise RuntimeError(
                f"Not enough history to train: {len(labeled):,} labeled rows / "
                f"{len(offsets):,} bars"
            )

        split = max(60, int(len(offsets) * 0.8))
        train = training_rows(rows, split)
        validation = [
            row
            for row in rows
            if split <= row.offset < len(offsets) and row.label is not None
        ]
        if not train or not validation:
            raise RuntimeError("Walk-forward split produced empty train or validation sets")
        del rows

        def matrix(samples):
            return np.asarray([row.features for row in samples], dtype=float)

        def target(samples):
            # Same within-session rank target used by the offline experiment.
            by_offset: dict[int, list[int]] = defaultdict(list)
            for index, row in enumerate(samples):
                by_offset[row.offset].append(index)
            result = [0.0] * len(samples)
            for indices in by_offset.values():
                ordered = sorted(
                    indices, key=lambda index: (samples[index].label, samples[index].ticker)
                )
                denominator = max(1, len(ordered) - 1)
                for rank, index in enumerate(ordered):
                    result[index] = rank / denominator - 0.5
            return np.asarray(result, dtype=float)

        def make_model() -> MLPRegressor:
            return MLPRegressor(
                hidden_layer_sizes=(48, 24),
                activation="relu",
                solver="adam",
                alpha=1e-4,
                batch_size=512,
                learning_rate_init=1e-3,
                max_iter=120,
                early_stopping=True,
                n_iter_no_change=8,
                random_state=self.settings.seed,
            )

        train_matrix = matrix(train)
        means = train_matrix.mean(axis=0)
        scales = train_matrix.std(axis=0)
        scales[scales == 0] = 1.0
        validation_model = make_model()
        validation_model.fit((train_matrix - means) / scales, target(train))
        validation_matrix = (matrix(validation) - means) / scales
        predictions = validation_model.predict(validation_matrix)
        validation_metrics = self._validation_metrics(validation, predictions)
        del train_matrix, validation_matrix, predictions, validation_model

        # Refit on every labeled row so the live model uses the newest data.
        all_matrix = matrix(labeled)
        final_means = all_matrix.mean(axis=0)
        final_scales = all_matrix.std(axis=0)
        final_scales[final_scales == 0] = 1.0
        final_model = make_model()
        final_model.fit((all_matrix - final_means) / final_scales, target(labeled))

        bundle = {
            "model": final_model,
            "means": final_means,
            "scales": final_scales,
            "feature_names": FEATURE_NAMES,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "samples": len(labeled),
            "train_samples": len(train),
            "validation_samples": len(validation),
            "validation": validation_metrics,
            "data_start": session_dates[0],
            "data_end": session_dates[-1],
            "train_end_bar": int(up_to_bar),
            "training_seconds": round(time.time() - started, 1),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("wb") as handle:
            pickle.dump(bundle, handle, protocol=4)
        os.replace(temporary, self.path)
        with self._lock:
            self._bundle = bundle
            self._score_cache_key = None
            self._score_cache_values = {}
            self._status.update(
                {
                    "state": "ready",
                    "ready": True,
                    "trained_at": bundle["trained_at"],
                    "samples": bundle["samples"],
                    "train_samples": bundle["train_samples"],
                    "validation_samples": bundle["validation_samples"],
                    "validation": validation_metrics,
                    "data_start": bundle["data_start"],
                    "data_end": bundle["data_end"],
                    "trained_through_bar": bundle["train_end_bar"],
                    "error": None,
                }
            )
        logger.info(
            "Neural model ready: %s rows, validation IC %.4f",
            f"{len(labeled):,}",
            validation_metrics.get("rank_ic") or 0.0,
        )

    @staticmethod
    def _validation_metrics(rows, predictions) -> dict:
        groups: dict[int, list[tuple[float, float]]] = defaultdict(list)
        for value, row in zip(predictions, rows):
            if row.label is not None:
                groups[row.offset].append((float(value), float(row.label)))
        ics: list[float] = []
        top_excess: list[float] = []
        for pairs in groups.values():
            if len(pairs) < 30:
                continue
            values = [pair[0] for pair in pairs]
            labels = [pair[1] for pair in pairs]
            rank_values = sorted(range(len(values)), key=lambda index: values[index])
            rank_labels = sorted(range(len(labels)), key=lambda index: labels[index])
            value_rank = [0.0] * len(values)
            label_rank = [0.0] * len(labels)
            for rank, index in enumerate(rank_values):
                value_rank[index] = float(rank)
            for rank, index in enumerate(rank_labels):
                label_rank[index] = float(rank)
            mean_value = statistics.mean(value_rank)
            mean_label = statistics.mean(label_rank)
            numerator = sum(
                (value - mean_value) * (label - mean_label)
                for value, label in zip(value_rank, label_rank)
            )
            denominator = (
                sum((value - mean_value) ** 2 for value in value_rank)
                * sum((label - mean_label) ** 2 for label in label_rank)
            ) ** 0.5
            if denominator:
                ics.append(numerator / denominator)
            order = sorted(range(len(values)), key=lambda index: values[index], reverse=True)
            mean = statistics.mean(labels)
            top_excess.append(statistics.mean(labels[index] for index in order[:10]) - mean)
        if not ics:
            return {"days": 0, "rank_ic": None, "top10_excess_bps": None}
        return {
            "days": len(ics),
            "rank_ic": round(statistics.mean(ics), 4),
            "rank_ic_std": round(statistics.pstdev(ics), 4) if len(ics) > 1 else 0.0,
            "top10_excess_bps": round(statistics.mean(top_excess) * 10_000, 1)
            if top_excess
            else None,
        }

    # ----------------------------------------------------------------- inference
    def score_context(self, context) -> dict[str, float]:
        with self._lock:
            bundle = self._bundle
        if bundle is None:
            return {}
        # A model trained through bar N must not be used to score bar N or an
        # earlier replay bar. It becomes live on the next unseen decision.
        if context.bar_index <= int(bundle.get("train_end_bar", -1)):
            return {}
        # Forecast refresh and the trading decision can ask for the same bar.
        # Include mutable live-context fields so an updated forming bar misses.
        cache_key = (
            context.bar_index,
            bundle.get("trained_at"),
            context.sim_time,
            len(context.news),
            round(sum(context.prices.values()), 4),
        )
        with self._lock:
            if self._score_cache_key == cache_key:
                return dict(self._score_cache_values)
        vectors = build_live_features(context)
        if not vectors:
            return {}
        try:
            import numpy as np

            tickers = list(vectors)
            matrix = np.asarray([vectors[ticker] for ticker in tickers], dtype=float)
            normalized = (matrix - bundle["means"]) / bundle["scales"]
            predictions = bundle["model"].predict(normalized)
            scores = {
                ticker: float(value) if np.isfinite(float(value)) else 0.0
                for ticker, value in zip(tickers, predictions)
            }
            with self._lock:
                self._score_cache_key = cache_key
                self._score_cache_values = scores
            return dict(scores)
        except Exception:
            logger.exception("Neural model inference failed")
            return {}
