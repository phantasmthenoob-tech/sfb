import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { money, signedMoney, simDate, toneClass } from "../lib/format";
import type { Order, Snapshot, Trade } from "../types";
import { Empty, Panel } from "./ui";

export function Activity({ snapshot }: { snapshot: Snapshot }) {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const barBucket = Math.floor(snapshot.simulation.bar_index / 2);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      apiGet<{ trades: Trade[] }>("/api/trades?limit=12"),
      apiGet<{ orders: Order[] }>("/api/orders?limit=12"),
    ])
      .then(([tradeData, orderData]) => {
        if (!cancelled) {
          setTrades(tradeData.trades);
          setOrders(orderData.orders);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [barBucket]);

  return (
    <div className="stack">
      <Panel title="Fills">
        {trades.length === 0 ? (
          <Empty>No trades yet.</Empty>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Account</th>
                <th>Side</th>
                <th>Ticker</th>
                <th className="num">Shares</th>
                <th className="num">Price</th>
                <th className="num">P&L</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => (
                <tr key={trade.id}>
                  <td className="mono muted">{simDate(trade.sim_time)}</td>
                  <td>{trade.portfolio_name ?? "—"}</td>
                  <td>{trade.side}</td>
                  <td className="ticker">{trade.ticker}</td>
                  <td className="num mono">{trade.quantity}</td>
                  <td className="num mono">{money(trade.price)}</td>
                  <td className={`num mono ${toneClass(trade.realized_pnl)}`}>
                    {trade.realized_pnl ? signedMoney(trade.realized_pnl) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <Panel title="Orders">
        {orders.length === 0 ? (
          <Empty>No orders yet.</Empty>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Account</th>
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
                  <td>{order.portfolio_name ?? "—"}</td>
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
