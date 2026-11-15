import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import type { ModelStatus } from "../types";
import { Empty, Panel } from "./ui";

function stateLabel(state: ModelStatus["state"] | undefined) {
  if (!state) return "Loading";
  if (state === "ready") return "Ready";
  if (state === "training") return "Training";
  if (state === "error") return "Error";
  return "Not trained";
}

export function Models() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const next = await apiGet<ModelStatus>("/api/models/status");
      setStatus(next);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load model status");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (status?.state !== "training") return;
    const timer = window.setInterval(() => void load(), 2500);
    return () => window.clearInterval(timer);
  }, [status?.state, load]);

  const train = async () => {
    setBusy(true);
    setError(null);
    try {
      const next = await apiPost<ModelStatus>("/api/models/train");
      setStatus(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Training could not start");
    } finally {
      setBusy(false);
    }
  };

  const validation = status?.validation;
  const training = status?.state === "training" || busy;

  return (
    <div className="stack">
      <Panel
        title="Neural AI model"
        aside={<span className="caption">Live agent · retrainable</span>}
      >
        <p className="data-note">
          Neural AI trains from the bars and headlines already recorded in the
          simulation database. Training uses a chronological 80/20 split,
          validates with a rank-IC and top-ten excess-return check, then refits
          on all labeled history before atomically replacing the live artifact.
          The previous model stays active if training fails.
        </p>
        {error && <p className="error">{error}</p>}
        {!status ? (
          <Empty>Loading model status…</Empty>
        ) : (
          <>
            <dl className="account-lines">
              <div>
                <dt>Status</dt>
                <dd>{stateLabel(status.state)}</dd>
              </div>
              <div>
                <dt>Training rows</dt>
                <dd className="mono">{status.samples.toLocaleString()}</dd>
              </div>
              <div>
                <dt>Validation rows</dt>
                <dd className="mono">{status.validation_samples.toLocaleString()}</dd>
              </div>
              <div>
                <dt>Features</dt>
                <dd className="mono">{status.features}</dd>
              </div>
              <div>
                <dt>Data window</dt>
                <dd className="mono">
                  {status.data_start && status.data_end
                    ? `${status.data_start} → ${status.data_end}`
                    : "—"}
                </dd>
              </div>
              <div>
                <dt>Trained through bar</dt>
                <dd className="mono">{status.trained_through_bar ?? "—"}</dd>
              </div>
              <div>
                <dt>Trained at</dt>
                <dd className="mono">
                  {status.trained_at
                    ? new Date(status.trained_at).toLocaleString()
                    : "—"}
                </dd>
              </div>
              <div>
                <dt>Validation IC</dt>
                <dd className="mono">
                  {validation?.rank_ic == null
                    ? "—"
                    : validation.rank_ic.toFixed(4)}
                </dd>
              </div>
              <div>
                <dt>Top-10 excess</dt>
                <dd className="mono">
                  {validation?.top10_excess_bps == null
                    ? "—"
                    : `${validation.top10_excess_bps.toFixed(1)} bps`}
                </dd>
              </div>
            </dl>
            <div className="order-buttons">
              <button type="button" disabled={training} onClick={() => void train()}>
                {training ? "Training…" : "Retrain neural model"}
              </button>
            </div>
            <p className="data-note">
              A freshly trained model is used by Neural AI on its next decision.
              No model means Neural AI stays idle; the other three agents keep
              trading normally. The default full-history replay starts at bar 0,
              trains automatically once it has enough history, and then retrains
              automatically as the replay advances.
            </p>
          </>
        )}
      </Panel>
    </div>
  );
}
