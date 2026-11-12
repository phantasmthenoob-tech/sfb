import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { money, simDate, signedPct, toneClass } from "../lib/format";
import type { MarketBar, Snapshot } from "../types";
import { PriceChart } from "./PriceChart";
import { Empty, Panel } from "./ui";

interface HistoryResponse {
  ticker: string;
  bars: MarketBar[];
  sma5: number | null;
  sma20: number | null;
}

export function Markets({ snapshot }: { snapshot: Snapshot }) {
  const quotes = snapshot.quotes;
  const isLive = snapshot.simulation.mode === "live";
  const [ticker, setTicker] = useState(quotes[0]?.ticker ?? "AAPL");
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const barBucket = Math.floor(snapshot.simulation.bar_index / 2);
  const livePoll = snapshot.simulation.live?.last_poll;
  const liveOpen = snapshot.simulation.live?.market_open ?? false;

  useEffect(() => {
    if (quotes.length && !quotes.some((quote) => quote.ticker === ticker)) {
      setTicker(quotes[0].ticker);
    }
  }, [quotes, ticker]);

  useEffect(() => {
    let cancelled = false;
    setHistory(null);
    apiGet<HistoryResponse>(`/api/market/history/${ticker}?limit=240`)
      .then((data) => {
        if (!cancelled) setHistory(data);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [ticker, barBucket, livePoll]);

  const selected = quotes.find((quote) => quote.ticker === ticker);

  return (
    <div className="markets">
      <Panel title="Markets" aside={
        <span className="caption">
          {snapshot.data.label} · {isLive ? "live" : "daily"}
        </span>
      }>
        <ul className="ticker-list">
          {quotes.map((quote) => (
            <li key={quote.ticker}>
              <button
                type="button"
                className={`ticker-row ${quote.ticker === ticker ? "ticker-active" : ""}`}
                onClick={() => setTicker(quote.ticker)}
              >
                <span className="ticker">{quote.ticker}</span>
                <span className="mono">{money(quote.price)}</span>
                <span className={`mono small ${toneClass(quote.change_pct)}`}>
                  {signedPct(quote.change_pct)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel>
        {selected ? (
          <>
            <div className="quote-head">
              <div>
                <div className="quote-ticker">{selected.ticker}</div>
                <div className="quote-change mono">
                  {money(selected.price)}{" "}
                  <span className={toneClass(selected.change_pct)}>
                    {signedPct(selected.change_pct)}
                  </span>
                </div>
              </div>
              <span className="caption">
                {simDate(selected.ts)} {isLive ? (liveOpen ? "live" : "last close") : "close"}
              </span>
            </div>
            <PriceChart bars={history?.bars ?? []} />
            <div className="quote-stats">
              <Stat label="Open" value={money(selected.open)} />
              <Stat label="High" value={money(selected.high)} />
              <Stat label="Low" value={money(selected.low)} />
              <Stat label="Volume" value={selected.volume.toLocaleString()} />
              <Stat label="SMA 5" value={history?.sma5 ? money(history.sma5) : "—"} />
              <Stat label="SMA 20" value={history?.sma20 ? money(history.sma20) : "—"} />
            </div>
            <p className="data-note">
              {snapshot.data.note}
              {isLive ? "" : ` Updated ${snapshot.data.last_bar_date ?? "—"}.`}
            </p>
          </>
        ) : (
          <Empty>Waiting for prices…</Empty>
        )}
      </Panel>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="quote-stat">
      <span>{label}</span>
      <span className="mono">{value}</span>
    </div>
  );
}
