import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, wsMarketUrl } from "../api/client";
import type {
  DataSourceInfo,
  IndexQuote,
  LeaderboardEntry,
  Portfolio,
  Quote,
  SimulationState,
  Snapshot,
} from "../types";

interface OverviewResponse {
  simulation: SimulationState;
  quotes: Quote[];
  indices: IndexQuote[];
  data: DataSourceInfo;
}

interface LeaderboardResponse {
  entries: LeaderboardEntry[];
}

/**
 * Subscribes to the replay tick websocket and falls back to HTTP polling when
 * websockets are unavailable (for example behind a restrictive proxy).
 */
export function useMarketStream() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const connectedRef = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const [overview, leaderboard, manual] = await Promise.all([
        apiGet<OverviewResponse>("/api/market/overview"),
        apiGet<LeaderboardResponse>("/api/leaderboard"),
        apiGet<Portfolio>("/api/portfolios/manual"),
      ]);
      setSnapshot({
        type: "snapshot",
        simulation: overview.simulation,
        quotes: overview.quotes,
        indices: overview.indices,
        leaderboard: leaderboard.entries,
        manual,
        data: overview.data,
        server_time: new Date().toISOString(),
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backend unreachable");
    }
  }, []);

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;

    const connect = () => {
      if (disposed) return;
      socket = new WebSocket(wsMarketUrl());
      socket.onopen = () => {
        if (disposed) return;
        connectedRef.current = true;
        setConnected(true);
        setError(null);
      };
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as Snapshot;
          if (payload.type === "snapshot") {
            setSnapshot(payload);
            setError(null);
          }
        } catch {
          // Ignore malformed frames rather than dropping the stream.
        }
      };
      socket.onclose = () => {
        if (disposed) return;
        connectedRef.current = false;
        setConnected(false);
        retryTimer = window.setTimeout(connect, 2500);
      };
      socket.onerror = () => socket?.close();
    };

    connect();
    void refresh();
    const poll = window.setInterval(() => {
      if (!disposed && !connectedRef.current) void refresh();
    }, 3000);

    return () => {
      disposed = true;
      window.clearTimeout(retryTimer);
      window.clearInterval(poll);
      socket?.close();
    };
  }, [refresh]);

  return { snapshot, connected, error, refresh };
}
