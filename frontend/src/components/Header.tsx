import { simDate } from "../lib/format";
import type { SimulationMode, SimulationState } from "../types";

interface Props {
  simulation?: SimulationState;
  busy: boolean;
  onStart: () => void;
  onPause: () => void;
  onReset: () => void;
  onSpeed: (speed: number) => void;
  onMode: (mode: SimulationMode) => void;
  onRange: (preset: string) => void;
}

const STATUS_LABEL: Record<string, string> = {
  running: "Running",
  paused: "Paused",
  completed: "Complete",
};

export function Header({
  simulation,
  busy,
  onStart,
  onPause,
  onReset,
  onSpeed,
  onMode,
  onRange,
}: Props) {
  const mode = simulation?.mode ?? "replay";
  const live = simulation?.live;
  const isLive = mode === "live";
  const status = simulation?.status ?? "paused";
  const progress = simulation?.progress_pct ?? 0;
  const statusText = isLive
    ? live?.market_open
      ? "Live · market open"
      : "Live · market closed"
    : STATUS_LABEL[status] ?? status;

  return (
    <header className="topbar">
      <div className="brand">
        <h1>Market Simulator</h1>
        <span>AI paper trading</span>
      </div>

      <div className="clock">
        <span className="clock-time">{simDate(simulation?.sim_time)}</span>
        <span className="clock-status">{statusText}</span>
        {!isLive && simulation?.start_date && (
          <span className="clock-window" title="Selected replay window">
            {simDate(simulation.start_date)} – {simDate(simulation.end_date)}
          </span>
        )}
      </div>

      <div className="controls">
        <div className="speeds" role="group" aria-label="Data mode">
          <button
            type="button"
            className={`speed ${!isLive ? "speed-active" : ""}`}
            onClick={() => onMode("replay")}
            disabled={busy}
            title="Replay the last year of real daily closes"
          >
            Replay
          </button>
          <button
            type="button"
            className={`speed ${isLive ? "speed-active" : ""}`}
            onClick={() => onMode("live")}
            disabled={busy}
            title="Poll live Yahoo Finance quotes during the US session"
          >
            Live
          </button>
        </div>

        {!isLive && simulation?.range_options && simulation.range_options.length > 0 && (
          <label className="range-control">
            <span>Range</span>
            <select
              value={simulation.replay_preset ?? "all"}
              onChange={(event) => onRange(event.target.value)}
              disabled={busy}
              aria-label="Replay date range"
              title={
                simulation.range_options.find(
                  (option) => option.id === simulation.replay_preset,
                )?.description ?? "Replay date range"
              }
            >
              {simulation.range_options.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        )}

        {!isLive && (
          <div className="speeds" role="group" aria-label="Replay speed">
            {(simulation?.speed_options ?? [1, 5, 10, 30]).map((speed) => (
              <button
                key={speed}
                type="button"
                className={`speed ${simulation?.speed === speed ? "speed-active" : ""}`}
                onClick={() => onSpeed(speed)}
                disabled={busy}
              >
                {speed}×
              </button>
            ))}
          </div>
        )}

        {!isLive &&
          (status === "running" ? (
            <button type="button" className="btn" onClick={onPause} disabled={busy}>
              Pause
            </button>
          ) : (
            <button type="button" className="btn btn-dark" onClick={onStart} disabled={busy}>
              {status === "completed" ? "Restart" : "Start"}
            </button>
          ))}
        <button type="button" className="btn" onClick={onReset} disabled={busy}>
          Reset
        </button>
      </div>

      {!isLive && (
        <div className="progress" aria-hidden="true">
          <div style={{ width: `${Math.min(progress, 100)}%` }} />
        </div>
      )}
    </header>
  );
}
