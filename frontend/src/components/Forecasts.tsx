import { useState } from "react";
import { apiPost } from "../api/client";
import { money, signedMoney, signedPct, simDate, toneClass } from "../lib/format";
import type { AgentForecast, ForecastCall, ForecastMeta, Snapshot } from "../types";
import { Empty, Panel } from "./ui";

const DEFAULT_META: ForecastMeta = {
  price_lookback_sessions: 20,
  momentum_lookback_sessions: 10,
  news_lookback_sessions: 5,
  volatility_lookback_sessions: 20,
  forecast_horizon_sessions: 5,
  max_bars_loaded: 120,
  note: "Uses only bars and headlines at or before the current simulation time.",
};

function arrow(direction: ForecastCall["direction"]): string {
  if (direction === "UP") return "↑";
  if (direction === "DOWN") return "↓";
  return "→";
}

function callLabel(direction: ForecastCall["direction"]): string {
  if (direction === "UP") return "expects a rise";
  if (direction === "DOWN") return "expects a fall";
  return "expects little movement";
}

function callName(direction: ForecastCall["direction"]): string {
  if (direction === "UP") return "rise";
  if (direction === "DOWN") return "drop";
  return "flat";
}

export function Forecasts({
  snapshot,
  onRefresh,
}: {
  snapshot: Snapshot;
  onRefresh: () => Promise<void> | void;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);
  const meta = snapshot.forecast_meta ?? DEFAULT_META;
  const groups: AgentForecast[] = snapshot.forecasts ?? [];
  const calls = groups
    .flatMap((group) =>
      group.calls.map((call) => ({ ...call, agent_name: group.agent_name })),
    )
    .sort((a, b) => Math.abs(b.expected_pct) - Math.abs(a.expected_pct));
  const best = calls[0];

  const predictNow = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await apiPost<{ forecasts: AgentForecast[] }>(
        "/api/market/forecasts/refresh",
      );
      await onRefresh();
      setMessage({
        text: result.forecasts?.length
          ? "Fresh calls from the latest visible bars. No orders were placed."
          : "Not enough visible history yet; start or advance the simulation first.",
      });
    } catch (err) {
      setMessage({
        text: err instanceof Error ? err.message : "Could not run a prediction.",
        error: true,
      });
    } finally {
      setBusy(false);
    }
  };

  const tools = (
    <div className="forecast-tools">
      <div className="forecast-lookback">
        <span>
          <strong>Price</strong> {meta.price_lookback_sessions} sessions
        </span>
        <span>
          <strong>Momentum</strong> {meta.momentum_lookback_sessions} sessions
        </span>
        <span>
          <strong>News</strong> {meta.news_lookback_sessions} sessions
        </span>
        <span>
          <strong>Volatility</strong> {meta.volatility_lookback_sessions} sessions
        </span>
        <span>
          <strong>Horizon</strong> {meta.forecast_horizon_sessions} sessions
        </span>
      </div>
      <div className="forecast-actions">
        {message && (
          <span
            className={`forecast-status ${message.error ? "forecast-status-error" : ""}`}
            role="status"
          >
            {message.text}
          </span>
        )}
        <button
          className="btn btn-dark"
          type="button"
          onClick={() => void predictNow()}
          disabled={busy}
        >
          {busy ? "Predicting…" : "Predict now"}
        </button>
      </div>
    </div>
  );

  if (!best) {
    return (
      <div className="forecasts">
        {tools}
        <Panel
          title="Forecasts"
          aside={<span className="caption">{simDate(snapshot.simulation.sim_time)}</span>}
        >
          <Empty>
            No calls yet. Press “Predict now” to run the AIs on the latest visible
            bars, or start the replay and let them rank their five biggest expected
            moves before each trading day&apos;s orders.
          </Empty>
        </Panel>
      </div>
    );
  }

  const bestMove = Math.abs(best.expected_pct).toFixed(2);

  return (
    <div className="forecasts">
      {tools}
      <Panel
        title="Biggest expected win"
        aside={<span className="caption">{simDate(best.sim_time)}</span>}
      >
        <div className="forecast-hero">
          <div className={`forecast-move mono ${toneClass(best.expected_pct)}`}>
            <span className="forecast-arrow">{arrow(best.direction)}</span>
            {bestMove}%
          </div>
          <div className="forecast-hero-copy">
            <div className="forecast-ticker">
              {best.ticker}
              <span className="tag">{best.agent_name}</span>
            </div>
            <p className="forecast-copy">
              {best.agent_name} {callLabel(best.direction)} of about {bestMove}% over the
              next {meta.forecast_horizon_sessions} sessions, a move of{" "}
              {signedMoney(best.expected_usd)} per share.
              {best.direction === "DOWN" ? " A short would target that move." : ""}
            </p>
            <p className="caption">
              {(best.confidence * 100).toFixed(0)}% confidence · {best.rationale}
            </p>
          </div>
        </div>
      </Panel>

      <div className="forecast-grid">
        {groups.map((group) => (
          <Panel
            key={group.agent_id}
            title={group.agent_name}
            aside={<span className="caption">{group.model_type}</span>}
          >
            <ol className="forecast-list">
              {group.calls.map((call) => (
                <li className="forecast-call" key={`${call.rank}-${call.ticker}`}>
                  <span className="forecast-rank">{call.rank}</span>
                  <div className="forecast-call-body">
                    <div className="forecast-call-line">
                      <span>
                        <span className="ticker">{call.ticker}</span>{" "}
                        <span className="caption">{callName(call.direction)}</span>
                      </span>
                      <span className={`mono ${toneClass(call.expected_pct)}`}>
                        {signedPct(call.expected_pct)}
                      </span>
                    </div>
                    <div className="forecast-call-sub">
                      <span className="mono">{money(call.price)} / share</span>
                      <span className={`mono ${toneClass(call.expected_usd)}`}>
                        {signedMoney(call.expected_usd)} est.
                      </span>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </Panel>
        ))}
      </div>

      <p className="data-note">
        Top five calls per AI, ranked by absolute expected move. Percent and per-share
        estimate use signal strength × recent {meta.volatility_lookback_sessions}-session
        volatility over {meta.forecast_horizon_sessions} sessions. Price signals use{" "}
        {meta.price_lookback_sessions} sessions of closes and{" "}
        {meta.momentum_lookback_sessions}-session momentum; news uses the last{" "}
        {meta.news_lookback_sessions} sessions. {meta.note} The engine loads up to{" "}
        {meta.max_bars_loaded} bars, but each model only reads its own window. “Predict now”
        refreshes calls without placing orders. A drop is a candidate short. Headlines are
        simulated. Not investment advice.
      </p>
    </div>
  );
}
