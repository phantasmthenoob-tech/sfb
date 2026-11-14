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

export interface ReplayRangeOption {
  id: string;
  label: string;
  description: string;
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
  data_start_date?: string;
  data_end_date?: string;
  progress_pct: number;
  decision_every_bars: number;
  replay_preset?: string;
  range_start_bar?: number;
  range_end_bar?: number;
  range_bars?: number;
  range_options?: ReplayRangeOption[];
}

export interface Quote {
  ticker: string;
  name?: string;
  kind?: "stock" | "etf";
  sector?: string | null;
  exposures?: string[];
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

export interface RecordingInfo {
  enabled: boolean;
  bars: number;
  sessions: number;
  tickers: number;
  first_date: string | null;
  last_date: string | null;
  last_recorded_at: string | null;
  note: string;
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
  recording?: RecordingInfo;
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

export interface ForecastMeta {
  price_lookback_sessions: number;
  momentum_lookback_sessions: number;
  news_lookback_sessions: number;
  volatility_lookback_sessions: number;
  forecast_horizon_sessions: number;
  max_bars_loaded: number;
  note: string;
}

export interface ForecastScorecardAgent {
  agent_id: number;
  agent_name: string;
  model_type: string;
  settled_calls: number;
  hits: number;
  hit_rate_pct: number | null;
  avg_abs_error_pct: number | null;
  avg_abs_move_pct: number | null;
  open_calls: number;
}

export interface ForecastScorecard {
  horizon_sessions: number;
  settled_calls: number;
  open_calls: number;
  agents: ForecastScorecardAgent[];
  sim_time: string | null;
  generated_at: string;
}

export interface TickerMeta {
  ticker: string;
  name: string;
  kind: "stock" | "etf";
  sector: string | null;
  exposures: string[];
}

export interface UniverseMeta {
  stocks: TickerMeta[];
  etfs: TickerMeta[];
  sectors: string[];
  exposures: string[];
}

export interface SectorAgentPerformance {
  agent_id: number;
  agent_name: string;
  model_type: string;
  sector: string;
  contribution_pct: number;
  realized_pnl: number;
  unrealized_pnl: number;
  fees: number;
  positions_value: number;
  trades: number;
  open_positions: number;
}

export interface SectorPerformance {
  agents: { id: number; name: string; model_type: string }[];
  sectors: {
    sector: string;
    exposures: string[];
    agents: SectorAgentPerformance[];
  }[];
  note: string;
}

export interface CorrelationSummary {
  window_sessions: number;
  tickers: number;
  pairs: number;
  average_pairwise_correlation: number;
  same_sector_average: number | null;
  cross_sector_average: number | null;
  top_pairs: { left: string; right: string; correlation: number }[];
  bottom_pairs: { left: string; right: string; correlation: number }[];
  note: string;
}

export interface Snapshot {
  type: "snapshot";
  simulation: SimulationState;
  quotes: Quote[];
  indices: IndexQuote[];
  forecasts: AgentForecast[];
  forecast_meta?: ForecastMeta;
  leaderboard: LeaderboardEntry[];
  manual: Portfolio | null;
  data: DataSourceInfo;
  universe_meta?: UniverseMeta;
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
