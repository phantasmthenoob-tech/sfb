# API Reference

Base URL: `http://localhost:8000` in local development, or the deployed backend origin.

Interactive OpenAPI documentation is available at `/docs` and the schema at `/openapi.json` while the backend is running. All normal responses are JSON. The manual order endpoint is unauthenticated and intended for a single-tenant demo.

## System

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Service status, simulation state and public settings |
| GET | `/` | Service name, docs path and WebSocket path |

## Market data

| Method | Path | Parameters | Purpose |
| --- | --- | --- | --- |
| GET | `/api/market/overview` | — | Quotes, indices, forecasts, universe metadata and data-source state |
| GET | `/api/market/universe` | — | 120 stocks, 8 ETFs, sectors, exposure tags |
| GET | `/api/market/sectors` | — | Per-agent sector attribution |
| GET | `/api/market/correlations` | `window` 10–250, default 60 | Average pairwise and same/cross-sector correlation |
| GET | `/api/market/quote/{ticker}` | ticker | Current visible bar and metadata |
| GET | `/api/market/history/{ticker}` | `limit` 1–780, optional `from_bar` | Visible bars and SMA5/SMA20 |
| GET | `/api/market/news/{ticker}` | `limit` 1–100; `ALL` or `MARKET` | Visible simulated headlines |
| POST | `/api/market/forecasts/refresh` | — | Record fresh calls without trading |
| GET | `/api/market/forecasts/scorecard` | — | Settled forecast accuracy and open calls |

## Agents and portfolios

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/agents` | Four agents and their portfolios |
| GET | `/api/agents/{agent_id}` | Agent detail |
| GET | `/api/agents/{agent_id}/portfolio` | Portfolio for one agent |
| GET | `/api/agents/{agent_id}/predictions` | Prediction history |
| GET | `/api/leaderboard` | Ranked agent and manual accounts |
| GET | `/api/portfolios` | All portfolios |
| GET | `/api/portfolios/manual` | Manual account |
| GET | `/api/portfolios/{portfolio_id}` | One portfolio with positions and equity curve |

## Orders and activity

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/orders` | Queue a manual market order |
| GET | `/api/orders` | Order history; optional `portfolio_id`, `limit` |
| GET | `/api/trades` | Fill history; optional `portfolio_id`, `limit` |
| GET | `/api/predictions` | Prediction history; optional `agent_id`, `limit` |

Manual order body:

```json
{
  "ticker": "AAPL",
  "side": "BUY",
  "quantity": 5,
  "portfolio_id": 4
}
```

`side` is one of `BUY`, `SELL`, `SHORT` or `COVER`. `portfolio_id` is optional and defaults to the manual portfolio. Agent portfolios reject manual orders. Orders fill on the next replay bar or live poll and pay 5 bps per side.

## Models

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/models/status` | Neural AI state, sample counts, validation metrics, data cutoff and artifact path |
| POST | `/api/models/train` | Start background training from history up to the current replay cursor; returns `202` |

`POST /api/models/train` is idempotent while a run is active: it returns the
current `training` status instead of starting a second thread. Poll
`/api/models/status` until `state` becomes `ready` or `error`.

## Simulation control

| Method | Path | Body | Purpose |
| --- | --- | --- | --- |
| GET | `/api/simulation/status` | — | Clock, mode, speed, progress and replay window |
| POST | `/api/simulation/start` | — | Start/resume; restart a completed replay |
| POST | `/api/simulation/pause` | — | Pause replay |
| POST | `/api/simulation/reset` | — | Reset accounts and return to the selected window start |
| POST | `/api/simulation/speed` | `{"speed": 5}` | Set 1, 5, 10 or 30 |
| POST | `/api/simulation/mode` | `{"mode": "live"}` | Switch replay/live; resets accounts |
| POST | `/api/simulation/range` | `{"preset": "1w"}` | Select `1w`, `1m`, `3m`, `ytd`, `1y`, `5y` or `all` |

## WebSocket

`/ws/market` sends a complete snapshot on connect and after simulation updates. Frames have `type: "snapshot"` and include:

- `simulation`: status, mode, speed, cursor, dates and range metadata
- `quotes`: 128 current quotes with stock/ETF and sector metadata
- `indices`: synthetic S&P/NASDAQ-style levels
- `forecasts` and `forecast_meta`
- `leaderboard` and `manual`
- `data`: source, recording coverage and live state
- `universe_meta`: stock/ETF classifications

The client reconnects after 2.5 seconds and uses REST polling while the socket is unavailable. Full snapshots make reconnects self-recovering; there is no delta protocol.

## Common errors

| Status | Meaning |
| --- | --- |
| 400 | Invalid mode/speed/range, rejected order, or non-manual portfolio order |
| 404 | Unknown ticker, agent, portfolio or missing historical bar |
| 422 | Request validation failure |
| 503 | Backend or data source unavailable |
