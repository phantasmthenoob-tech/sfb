import { money, signedPct, toneClass } from "../lib/format";
import type { LeaderboardEntry } from "../types";
import { Empty, Panel } from "./ui";

export function Leaderboard({ entries }: { entries: LeaderboardEntry[] }) {
  return (
    <Panel title="Leaderboard" aside={<span className="caption">Ranked by return</span>}>
      {entries.length === 0 ? (
        <Empty>No accounts yet.</Empty>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th className="rank">#</th>
              <th>Account</th>
              <th className="num">Equity</th>
              <th className="num">Return</th>
              <th className="num">Max DD</th>
              <th className="num">Trades</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id} className={entry.kind === "manual" ? "row-you" : undefined}>
                <td className="rank">{entry.rank}</td>
                <td>
                  {entry.kind === "manual" ? "You" : entry.name}
                  {entry.kind === "manual" && <span className="tag">manual</span>}
                </td>
                <td className="num mono">{money(entry.equity)}</td>
                <td className={`num mono ${toneClass(entry.total_return_pct)}`}>
                  {signedPct(entry.total_return_pct)}
                </td>
                <td className="num mono muted">
                  {entry.max_drawdown_pct === 0 ? "0.00%" : `-${entry.max_drawdown_pct.toFixed(2)}%`}
                </td>
                <td className="num mono">{entry.total_trades}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}
