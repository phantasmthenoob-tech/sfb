import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { money, simDate, signedPct, toneClass } from "../lib/format";
import type { CorrelationSummary, MarketBar, Snapshot } from "../types";
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
  const [kind, setKind] = useState<"stock" | "etf">("stock");
  const [sector, setSector] = useState("All");
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [correlation, setCorrelation] = useState<CorrelationSummary | null>(null);
  const barBucket = Math.floor(snapshot.simulation.bar_index / 2);
  const rangeStart = snapshot.simulation.range_start_bar;
  const correlationBucket = Math.floor(snapshot.simulation.bar_index / 20);
  const livePoll = snapshot.simulation.live?.last_poll;
  const liveOpen = snapshot.simulation.live?.market_open ?? false;
  const sectors = snapshot.universe_meta?.sectors ?? [];
  const visible = quotes.filter(
    (quote) =>
      (quote.kind ?? "stock") === kind &&
      (kind === "etf" || sector === "All" || quote.sector === sector),
  );

  useEffect(() => {
    if (visible.length && !visible.some((quote) => quote.ticker === ticker)) {
      setTicker(visible[0].ticker);
    }
  }, [visible, ticker]);

  useEffect(() => {
    let cancelled = false;
    apiGet<CorrelationSummary>("/api/market/correlations?window=60")
      .then((result) => {
        if (!cancelled) setCorrelation(result);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [correlationBucket]);

  useEffect(() => {
    let cancelled = false;
    setHistory(null);
    const fromBar = rangeStart === undefined ? "" : `&from_bar=${rangeStart}`;
    apiGet<HistoryResponse>(`/api/market/history/${ticker}?limit=240${fromBar}`)
      .then((data) => {
        if (!cancelled) setHistory(data);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [ticker, barBucket, livePoll, rangeStart]);

  const selected = quotes.find((quote) => quote.ticker === ticker);

  return (
    <div className="markets">
      <Panel title="Markets" aside={
        <span className="caption">
          {snapshot.data.recording?.enabled && (
            <span className="recording-status" title={snapshot.data.recording.note}>
              ● Recording {snapshot.data.recording.bars.toLocaleString()}
            </span>
          )}{" "}
          {snapshot.data.label} · {isLive ? "live" : "daily"}
        </span>
      }>
        <div className="market-filters">
          <div className="kind-toggle">
            <button
              type="button"
              className={kind === "stock" ? "filter-active" : ""}
              onClick={() => setKind("stock")}
            >
              Stocks
            </button>
            <button
              type="button"
              className={kind === "etf" ? "filter-active" : ""}
              onClick={() => setKind("etf")}
            >
              ETFs
            </button>
          </div>
          {kind === "stock" && (
            <select value={sector} onChange={(event) => setSector(event.target.value)} aria-label="Sector">
              <option value="All">All sectors</option>
              {sectors.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          )}
        </div>
        <ul className="ticker-list">
          {visible.map((quote) => (
            <li key={quote.ticker}>
              <button
                type="button"
                className={`ticker-row ${quote.ticker === ticker ? "ticker-active" : ""}`}
                onClick={() => setTicker(quote.ticker)}
                title={quote.name ?? quote.ticker}
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
        <p className="data-note">{visible.length} {kind === "stock" ? "stocks" : "ETF benchmarks"} shown.</p>
      </Panel>

      <Panel>
        {selected ? (
          <>
            <div className="quote-head">
              <div>
                <div className="quote-ticker">{selected.ticker}</div>
                <div className="quote-name">{selected.name ?? selected.ticker}</div>
                {selected.sector && <div className="quote-sector">{selected.sector}</div>}
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
            {selected.exposures && selected.exposures.length > 0 && (
              <div className="exposure-tags">
                {selected.exposures.map((tag) => (
                  <span key={tag} className="tag">
                    {tag}
                  </span>
                ))}
              </div>
            )}
            {correlation && (
              <div className="correlation-strip">
                <span>60-session average pairwise correlation</span>
                <strong className="mono">{correlation.average_pairwise_correlation.toFixed(3)}</strong>
                <span className="muted">
                  {correlation.top_pairs[0]
                    ? `Top: ${correlation.top_pairs[0].left}/${correlation.top_pairs[0].right} ${correlation.top_pairs[0].correlation.toFixed(2)}`
                    : "Not enough bars"}
                </span>
              </div>
            )}
            <p className="data-note">
              {snapshot.data.note}
              {isLive ? "" : ` Updated ${snapshot.data.last_bar_date ?? "—"}.`}
              {snapshot.data.recording &&
                ` ${snapshot.data.recording.sessions.toLocaleString()} sessions recorded through ${snapshot.data.recording.last_date ?? "—"}.`}
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
