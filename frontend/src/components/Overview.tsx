import { money, signedPct, toneClass } from "../lib/format";
import type { Snapshot } from "../types";
import { Leaderboard } from "./Leaderboard";
import { Empty, Panel } from "./ui";

export function Overview({ snapshot }: { snapshot: Snapshot }) {
  const { leaderboard, quotes, manual } = snapshot;

  return (
    <div className="overview">
      <Leaderboard entries={leaderboard} />

      <div className="stack">
        <Panel title="Markets">
          {quotes.length === 0 ? (
            <Empty>Waiting for prices…</Empty>
          ) : (
            <ul className="quote-list">
              {quotes.map((quote) => (
                <li key={quote.ticker}>
                  <span className="ticker">{quote.ticker}</span>
                  <span className="mono">{money(quote.price)}</span>
                  <span className={`mono ${toneClass(quote.change_pct)}`}>
                    {signedPct(quote.change_pct)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Your account">
          <dl className="account-lines">
            <div>
              <dt>Equity</dt>
              <dd className="mono">{money(manual?.equity ?? 0)}</dd>
            </div>
            <div>
              <dt>Cash</dt>
              <dd className="mono">{money(manual?.cash ?? 0)}</dd>
            </div>
            <div>
              <dt>Positions</dt>
              <dd className="mono">{manual?.positions.length ?? 0}</dd>
            </div>
          </dl>
        </Panel>
      </div>
    </div>
  );
}
