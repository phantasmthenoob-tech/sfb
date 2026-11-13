export type SimulationStatus = "running" | "paused" | "completed";
export type SimulationMode = "replay" | "live";
export type Side = "BUY" | "SELL" | "SHORT" | "COVER";
export type Tab = "forecasts" | "leaderboard" | "markets" | "trading" | "activity";

export interface LiveState {
  market_open: boolean;
  last_poll: string | null;
  session_date: string | null;
  poll_seconds: number;
  decision_seconds: number;
  last_decision: string | null;
  error: string | null;
  next_poll_in?: number;
  reference?: string;
}

export interface SimulationState {
  status: SimulationStatus;
  mode: SimulationMode;
  live?: LiveState;
  speed: number;
  speed_options: number[];
  bar_index: number;
  total_bars: number;
  sim_time: string;
  session_date: string;
  start_date: string;
  end_date: string;
  progress_pct: number;
  decision_every_bars: number;
}

export interface Quote {
  ticker: string;
  price: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  previous_close: number | null;
  change: number;
  change_pct: number;
  ts: string;
}

export interface IndexQuote {
  symbol: string;
  name: string;
  level: number;
  change_pct: number;
}

export interface Position {
  ticker: string;
  quantity: number;
  side: "LONG" | "SHORT";
  average_entry: number;
  price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pct: number;
}

export interface EquityPoint {
  ts: string;
  bar_index: number;
  equity: number;
}

export interface Portfolio {
  id: number;
  name: string;
  kind: "agent" | "manual";
  agent_id: number | null;
  model_type: string | null;
  cash: number;
  positions_value: number;
  equity: number;
  starting_balance: number;
  total_return_pct: number;
  realized_pnl: number;
  unrealized_pnl: number;
  win_rate_pct: number;
  max_drawdown_pct: number;
  total_trades: number;
  closed_trades: number;
  fees_paid: number;
  borrow_fees: number;
  short_exposure: number;
  positions: Position[];
  equity_curve?: EquityPoint[];
}

export interface LeaderboardEntry extends Portfolio {
  rank: number;
}

export interface DataSourceInfo {
  source: string;
  label: string;
  interval: string;
  bar_count: number;
  fetched_at: string | null;
  last_bar_date: string | null;
  refresh_hours: number;
  note: string;
  stale: boolean;
  live?: LiveState;
}

export interface ForecastCall {
  rank: number;
  ticker: string;
  direction: "UP" | "DOWN" | "FLAT";
  expected_pct: number;
  price: number;
  expected_usd: number;
  confidence: number;
  rationale: string;
  sim_time: string;
  bar_index: number;
}

export interface AgentForecast {
  agent_id: number;
  agent_name: string;
  model_type: string;
  calls: ForecastCall[];
}

export interface Snapshot {
  type: "snapshot";
  simulation: SimulationState;
  quotes: Quote[];
  indices: IndexQuote[];
  forecasts: AgentForecast[];
  leaderboard: LeaderboardEntry[];
  manual: Portfolio | null;
  data: DataSourceInfo;
  server_time: string;
}

export interface MarketBar {
  ts: string;
  session_date: string;
  bar_index: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Order {
  id: number;
  portfolio_id: number;
  portfolio_name?: string;
  ticker: string;
  side: Side;
  quantity: number;
  status: "PENDING" | "FILLED" | "REJECTED" | "CANCELLED";
  reason: string | null;
  source: string;
  sim_time: string;
  fill_price: number | null;
  fees: number;
}

export interface Trade {
  id: number;
  portfolio_name?: string;
  ticker: string;
  side: Side;
  quantity: number;
  price: number;
  fees: number;
  realized_pnl: number;
  sim_time: string;
}
