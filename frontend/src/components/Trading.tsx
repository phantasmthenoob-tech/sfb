import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { money, signedMoney, signedShares, simDate, toneClass } from "../lib/format";
import type { Order, Side, Snapshot } from "../types";
import { Empty, Panel } from "./ui";

const SIDES: { side: Side; label: string; className: string }[] = [
  { side: "BUY", label: "Buy", className: "btn-buy" },
  { side: "SELL", label: "Sell", className: "btn-sell" },
  { side: "SHORT", label: "Short", className: "btn-short" },
  { side: "COVER", label: "Cover", className: "btn-cover" },
];

export function Trading({ snapshot, onRefresh }: { snapshot: Snapshot; onRefresh: () => void }) {
  const manual = snapshot.manual;
  const quotes = snapshot.quotes;
  const [ticker, setTicker] = useState(quotes[0]?.ticker ?? "AAPL");
  const [quantity, setQuantity] = useState("5");
  const [busy, setBusy] = useState<Side | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const manualId = manual?.id;
  const barBucket = Math.floor(snapshot.simulation.bar_index / 2);
  const selected = quotes.find((quote) => quote.ticker === ticker);
  const parsedQuantity = Number.parseInt(quantity, 10);
  const isLive = snapshot.simulation.mode === "live";
  const completed = !isLive && snapshot.simulation.status === "completed";
  const livePoll = snapshot.simulation.live?.last_poll;
  const liveOpen = snapshot.simulation.live?.market_open ?? false;

  const loadOrders = useCallback(async () => {
    if (!manualId) return;
    try {
      const data = await apiGet<{ orders: Order[] }>(`/api/orders?portfolio_id=${manualId}&limit=6`);
      setOrders(data.orders);
    } catch {
      // Non-critical; retried on the next tick.
    }
  }, [manualId]);

  useEffect(() => {
    void loadOrders();
  }, [loadOrders, barBucket, livePoll]);

  useEffect(() => {
    if (quotes.length && !quotes.some((quote) => quote.ticker === ticker)) {
      setTicker(quotes[0].ticker);
    }
  }, [quotes, ticker]);

  const submit = async (side: Side) => {
    if (!manual) return;
    if (!Number.isFinite(parsedQuantity) || parsedQuantity <= 0) {
      setNotice("Enter a positive number of shares.");
      return;
    }
    setBusy(side);
    setNotice(null);
    try {
      const result = await apiPost<{ message: string }>("/api/orders", {
        ticker,
        side,
        quantity: parsedQuantity,
      });
      setNotice(result?.message ?? `${side} ${parsedQuantity} ${ticker} queued.`);
      onRefresh();
      window.setTimeout(() => {
        void loadOrders();
        onRefresh();
      }, 700);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Order failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="stack">
      <div className="trading-top">
        <Panel title="Trade">
          <div className="field">
            <label htmlFor="ticker">Ticker</label>
            <select id="ticker" value={ticker} onChange={(event) => setTicker(event.target.value)}>
              {quotes.map((quote) => (
                <option key={quote.ticker} value={quote.ticker}>
                  {quote.ticker}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="quantity">Shares</label>
            <input
              id="quantity"
              type="number"
              min={1}
              step={1}
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
            />
          </div>

          <p className="hint">
            {selected
              ? `${money(selected.price)} ${
                  isLive && liveOpen ? "live" : "last close"
                }`
              : "No price"}{" "}
            ·{" "}
            {isLive
              ? liveOpen
                ? "fills on the next quote"
                : "queued until the market opens"
              : "fills at the next day's open"}
          </p>

          <div className="order-buttons">
            {SIDES.map(({ side, label, className }) => (
              <button
                key={side}
                type="button"
                className={`btn ${className}`}
                disabled={busy !== null || completed}
                onClick={() => void submit(side)}
              >
                {busy === side ? "…" : label}
              </button>
            ))}
          </div>

          {completed && <p className="hint">Replay finished. Reset to trade again.</p>}
          {notice && <p className="notice">{notice}</p>}
        </Panel>

        <Panel title="Account">
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
              <dd className="mono">{money(manual?.positions_value ?? 0)}</dd>
            </div>
            <div>
              <dt>Return</dt>
              <dd className={`mono ${toneClass(manual?.total_return_pct ?? 0)}`}>
                {(manual?.total_return_pct ?? 0).toFixed(2)}%
              </dd>
            </div>
          </dl>
        </Panel>
      </div>

      <Panel title="Positions">
        {!manual || manual.positions.length === 0 ? (
          <Empty>No open positions.</Empty>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th className="num">Shares</th>
                <th className="num">Avg</th>
                <th className="num">Last</th>
                <th className="num">P&L</th>
              </tr>
            </thead>
            <tbody>
              {manual.positions.map((position) => (
                <tr key={position.ticker}>
                  <td className="ticker">{position.ticker}</td>
                  <td className="num mono">{signedShares(position.quantity)}</td>
                  <td className="num mono">{money(position.average_entry)}</td>
                  <td className="num mono">{money(position.price)}</td>
                  <td className={`num mono ${toneClass(position.unrealized_pnl)}`}>
                    {signedMoney(position.unrealized_pnl)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <Panel title="Recent orders">
        {orders.length === 0 ? (
          <Empty>No orders yet.</Empty>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Side</th>
                <th>Ticker</th>
                <th className="num">Shares</th>
                <th>Status</th>
                <th className="num">Fill</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id}>
                  <td className="mono muted">{simDate(order.sim_time)}</td>
                  <td>{order.side}</td>
                  <td className="ticker">{order.ticker}</td>
                  <td className="num mono">{order.quantity}</td>
                  <td className={order.status === "REJECTED" ? "neg" : ""}>
                    {order.status}
                    {order.reason && order.status === "REJECTED" && (
                      <span className="caption"> {order.reason.split(":")[0].replace(/_/g, " ")}</span>
                    )}
                  </td>
                  <td className="num mono">{order.fill_price ? money(order.fill_price) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
