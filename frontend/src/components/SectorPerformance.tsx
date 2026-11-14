import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { SectorPerformance as SectorPerformanceData, Snapshot } from "../types";
import { Empty, Panel } from "./ui";

export function SectorPerformance({ snapshot }: { snapshot: Snapshot }) {
  const [data, setData] = useState<SectorPerformanceData | null>(null);
  const bucket = Math.floor(snapshot.simulation.bar_index / 10);

  useEffect(() => {
    let cancelled = false;
    apiGet<SectorPerformanceData>("/api/market/sectors")
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [bucket]);

  const agents = data?.agents ?? [];
  return (
    <Panel
      title="Sector attribution"
      aside={<span className="caption">Contribution to return</span>}
    >
      {!data || data.sectors.length === 0 ? (
        <Empty>Waiting for sector trades…</Empty>
      ) : (
        <div className="sector-table-wrap">
          <table className="data-table sector-table">
            <thead>
              <tr>
                <th>Sector</th>
                {agents.map((agent) => (
                  <th key={agent.id} className="num">
                    {agent.name.replace(" AI", "")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.sectors.map((sector) => (
                <tr key={sector.sector}>
                  <td>
                    <div>{sector.sector}</div>
                    <div className="sector-tags">
                      {sector.exposures.slice(0, 3).map((tag) => (
                        <span key={tag} className="tag">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </td>
                  {agents.map((agent) => {
                    const row = sector.agents.find((entry) => entry.agent_id === agent.id);
                    return (
                      <td
                        key={agent.id}
                        className={`num mono ${row && row.contribution_pct < 0 ? "negative" : "positive"}`}
                      >
                        {row ? `${row.contribution_pct >= 0 ? "+" : ""}${row.contribution_pct.toFixed(2)}%` : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="data-note">{data?.note ?? "Sector attribution updates every ten replay bars."}</p>
    </Panel>
  );
}
