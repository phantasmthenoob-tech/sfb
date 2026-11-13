import { useCallback, useState } from "react";
import { apiPost } from "./api/client";
import { Activity } from "./components/Activity";
import { Forecasts } from "./components/Forecasts";
import { Header } from "./components/Header";
import { Markets } from "./components/Markets";
import { Overview } from "./components/Overview";
import { Trading } from "./components/Trading";
import { Loading } from "./components/ui";
import { useMarketStream } from "./hooks/useMarketStream";
import type { Tab } from "./types";

const TABS: { id: Tab; label: string }[] = [
  { id: "forecasts", label: "Forecasts" },
  { id: "leaderboard", label: "Leaderboard" },
  { id: "markets", label: "Markets" },
  { id: "trading", label: "Trading" },
  { id: "activity", label: "Activity" },
];

export default function App() {
  const { snapshot, error, refresh } = useMarketStream();
  const [tab, setTab] = useState<Tab>("leaderboard");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const action = useCallback(
    async (path: string, body?: unknown) => {
      setBusy(true);
      setActionError(null);
      try {
        await apiPost(path, body);
        await refresh();
      } catch (err) {
        setActionError(err instanceof Error ? err.message : "Action failed");
      } finally {
        setBusy(false);
      }
    },
    [refresh],
  );

  return (
    <div className="app">
      <Header
        simulation={snapshot?.simulation}
        busy={busy}
        onStart={() => void action("/api/simulation/start")}
        onPause={() => void action("/api/simulation/pause")}
        onReset={() => void action("/api/simulation/reset")}
        onSpeed={(speed) => void action("/api/simulation/speed", { speed })}
        onMode={(mode) => void action("/api/simulation/mode", { mode })}
      />

      <nav className="tabs" aria-label="Sections">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`tab ${tab === item.id ? "tab-active" : ""}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <main>
        {error && !snapshot && <p className="error">Cannot reach the backend. {error}</p>}
        {actionError && <p className="error">{actionError}</p>}

        {!snapshot ? (
          <Loading label="Connecting…" />
        ) : tab === "forecasts" ? (
          <Forecasts snapshot={snapshot} onRefresh={refresh} />
        ) : tab === "leaderboard" ? (
          <Overview snapshot={snapshot} />
        ) : tab === "markets" ? (
          <Markets snapshot={snapshot} />
        ) : tab === "trading" ? (
          <Trading snapshot={snapshot} onRefresh={refresh} />
        ) : (
          <Activity snapshot={snapshot} />
        )}
      </main>

    </div>
  );
}
