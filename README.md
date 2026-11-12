# AI Market Simulator

A paper-trading arena where three independent AI portfolios and one manual
portfolio compete from identical starting capital, either on a one-year
historical replay or against **live** Yahoo Finance quotes during the US
session.

This is the first milestone from the design doc: **a reliable trading engine,
a deterministic replay clock, manual buy/sell/short/cover, and a live
leaderboard**. The AI layer is wired in separately as interchangeable
strategies, so model work never touches the accounting code.

> Simulation only. Prices are real daily closes downloaded from Yahoo Finance;
> headlines are simulated and portfolios are fictitious. Not investment advice.

## What works today

- **Replay mode**: one year of daily OHLCV bars from Yahoo Finance, cached in
  SQLite and refreshed once per day. Only completed sessions are used, so
  portfolio values move once per trading day, not intraday.
- **Live mode**: the same engine polls real Yahoo Finance quotes every 60 s
  during the US session, marks portfolios to the latest print and fills orders
  on the next poll. Outside market hours it shows the last close and says so.
- Paper-trading engine with cash, long and short positions, fees, borrow costs
  and risk limits.
- Separate `orders` and `trades` tables: orders are intents, trades are fills.
- Market orders fill at the **next day's** open, never at a price the decision
  could already see.
- Replay clock gates prices, news, predictions and fills.
- Three agent portfolios (`Price AI`, `News AI`, `Combined AI`) at $10,000 each,
  plus a fourth **manual** portfolio with BUY / SELL / SHORT / COVER controls.
- Leaderboard by total return with realized/unrealized P&L, win rate, maximum
  drawdown and trade count.
- REST API + `/ws/market` websocket for live dashboard updates.
- Minimal TypeScript dashboard: Leaderboard, Markets, Trading, Activity.

## Architecture

```
frontend/ (React + TypeScript + Vite)
        REST /api/*  +  WebSocket /ws/market
                    │
backend/ (Python 3.12 + FastAPI)
  api/            HTTP + websocket endpoints
  services/       replay clock + event fan-out
  competition/    agent runner, rankings, metrics
  ai/             strategies (signals only)
  trading/        exchange, order manager, accounting, risk limits
  market/         Yahoo Finance daily data (cached), news, features
  database/       SQLite schema and repositories
```

Two rules keep the results meaningful:

1. **Agents never mutate portfolios.** They return `OrderIntent`s. The order
   manager and exchange validate and fill.
2. **The clock controls everything.** Every read is cut at the current replay
   bar, and every fill happens on the following bar.

## Quick start

### Backend

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt        # runtime only: requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API is at <http://localhost:8000>, interactive docs at `/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000, proxies /api and /ws to :8000
```

Open <http://localhost:3000>. Press **Start** if the replay boots paused.

To point the dashboard at a separate backend (for example Render), set:

```bash
VITE_API_BASE=https://your-api.onrender.com
VITE_WS_URL=wss://your-api.onrender.com/ws/market
```

Both are build-time variables; rebuild the static site after changing them.
Without them the app uses same-origin paths (the Vite proxy in development).

## Simulation rules

| Rule | Value |
| --- | --- |
| Starting capital | $10,000 per portfolio ($30,000 AI field + $10,000 manual) |
| Universe | AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, META, AMD |
| Market data | Yahoo Finance daily OHLCV, ~1 year, cached in SQLite |
| Refresh | Once every 24 h; only completed sessions are appended |
| Modes | **Replay** (history) or **Live** (real quotes, US session) |
| Replay | One bar = one real trading day (~251 sessions) |
| Live polling | Every 60 s while the market is open (`LIVE_POLL_SECONDS`) |
| Live decisions | Agents re-evaluate every 5 min (`LIVE_DECISION_SECONDS`) |
| Speeds | 1× / 5× / 10× / 30× (1 day per second at 1×) |
| Fees | 5 bps of notional per side |
| Short borrow | 8% annualized on short market value, charged per session |
| Position limits | 25% of equity per long, 20% per short, 50% total short |
| Order size | 25% of equity for orders that increase exposure |
| Order type | Market: next day's open in replay, next live quote in live mode |
| Direction rules | SELL only reduces longs; COVER only reduces shorts |

**Equity identity** (the property the tests enforce):

```
equity = starting_balance + realized_pnl + unrealized_pnl
         - fees_paid - borrow_fees
```

Short-sale proceeds are credited to cash and the liability is carried in the
negative position, so the same formula values long and short books.

### Replay vs live

The header has a **Replay / Live** switch. Switching modes resets the four
portfolios (trading history is discarded) because the two modes measure
different things:

- **Replay** walks the ~251 cached daily sessions. You control speed; a market
  order decided at one close fills at the next session's open.
- **Live** follows the real clock. Every `LIVE_POLL_SECONDS` the backend polls
  Yahoo Finance for the universe, updates one forming daily bar
  (open/high/low/close/volume), revalues positions and fills queued orders at
  the new prints. Every `LIVE_DECISION_SECONDS` the agents see the updated
  daily history plus today's live price and submit new intents. Weekends,
  holidays and after 16:00 ET the market is reported as closed and nothing is
  marked or filled until it reopens.

Live quotes come from the same unofficial Yahoo chart endpoint as the replay;
no API key is required. If Yahoo is unreachable the dashboard keeps the last
known prices and shows the error in the footer.

### How the agents work

The three agents are deterministic baselines behind one `BaseAgent` interface:

- **Price AI** — 5/20-bar SMA spread plus 10-bar momentum, ranked across the
  universe.
- **News AI** — average headline sentiment over a rolling 5-session window.
- **Combined AI** — 60% price score, 40% news score.

Each evaluates every trading day, records a prediction, and emits intents for
its own portfolio. They are intentionally simple: the point of this milestone is
that accounting is correct before any model tuning. Swapping in an ML model
means implementing `evaluate()` in `backend/app/ai/`.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Service + simulation status |
| GET | `/api/market/overview` | Indices, quotes, clock state |
| GET | `/api/market/quote/{ticker}` | Current replay price |
| GET | `/api/market/history/{ticker}?limit=240` | Bars visible so far |
| GET | `/api/market/news/{ticker}` | Headlines visible so far (`ALL` supported) |
| GET | `/api/agents` | Agent portfolios + latest prediction |
| GET | `/api/agents/{id}/portfolio` | Portfolio, positions, equity curve |
| GET | `/api/agents/{id}/predictions` | Prediction history |
| GET | `/api/leaderboard` | Rankings and all metrics |
| GET | `/api/portfolios/manual` | The manual account |
| POST | `/api/orders` | Submit a manual order |
| GET | `/api/orders` / `/api/trades` / `/api/predictions` | Activity logs |
| POST | `/api/simulation/start` · `/pause` · `/reset` · `/speed` | Clock controls |
| GET | `/api/simulation/status` | Clock state |
| WS | `/ws/market` | Snapshot on connect, then a frame per tick |

Manual order example:

```bash
curl -X POST localhost:8000/api/orders \
  -H 'Content-Type: application/json' \
  -d '{"ticker":"AAPL","side":"SHORT","quantity":5}'
```

The response is a `PENDING` order. It fills at the next day's open; then
`/api/trades` shows the fill. Rejected orders return HTTP 400 with a reason
(for example `insufficient_buying_power`).

## Database

SQLite (`backend/data/simulation.db` by default). Tables: `agents`,
`portfolios`, `positions`, `orders`, `trades`, `predictions`, `market_data`,
`news`, `data_cache`, `simulation_runs`, `portfolio_snapshots`.

`positions.quantity` is signed: `+` long, `-` short. Orders keep their status
(`PENDING`/`FILLED`/`REJECTED`/`CANCELLED`) and a rejection reason; trades are
immutable fills with fees and realized P&L.

## Tests

```bash
cd backend && . .venv/bin/activate && python -m pytest -q
```

Coverage focuses on accounting and replay correctness:

- buy/sell P&L, average entry, short proceeds and covering;
- fees, borrow fees and the equity identity;
- rejection paths: no position, over-sell, over-cover, buying power, position
  and short-exposure limits, conflicting long/short;
- next-day fills, clock/data gating, pause/reset, session borrow accrual,
  replay completion;
- Yahoo Finance daily-bar import, calendar alignment, cache reuse, daily
  append refresh, and the sample-data fallback;
- API + websocket contracts, manual order lifecycle, agent isolation.

## Deployment

The repo ships `render.yaml` with two Render services: the FastAPI backend and
the static dashboard. You can use the Blueprint or create each service by hand.

### Backend on Render

Blueprint: push the repo, then **New → Blueprint** in Render and pick the repo.
Render prompts for the `sync: false` values (`CORS_ORIGINS`, `VITE_API_BASE`,
`VITE_WS_URL`); set the frontend values after its URL exists.

Manual web service:

| Setting | Value |
| --- | --- |
| Root directory | `backend` |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/api/health` |
| Runtime | Python 3.12 |

Environment variables (all optional except CORS for a real frontend):

| Variable | Default | Purpose |
| --- | --- | --- |
| `CORS_ORIGINS` | `*` | Comma-separated **exact** browser origins allowed to call the API, e.g. `https://my-dashboard.onrender.com,https://preview.example.com`. Scheme required, no trailing slash. `*` is only for a throwaway demo. |
| `SIM_AUTOSTART` | `1` | `0` boots the replay paused; press **Start**. |
| `SIM_MODE` | `replay` | `replay` or `live` (live polls real quotes during the US session). |
| `MARKET_DATA_SOURCE` | `yahoo` | `yahoo` uses real daily bars; `synthetic` runs offline with sample prices. |
| `MARKET_DATA_REFRESH_HOURS` | `24` | How often to append newly completed daily sessions. |
| `MARKET_HISTORY_RANGE` | `1y` | Yahoo chart range used for the replay (`6mo`, `1y`, `2y`, …). |
| `LIVE_POLL_SECONDS` | `60` | Live quote poll interval while the market is open. |
| `LIVE_DECISION_SECONDS` | `300` | How often agents re-evaluate in live mode. |
| `DB_PATH` | `backend/data/simulation.db` | SQLite file (see persistence note). |
| `LOG_LEVEL` | `INFO` | Python log level. |

**Yahoo Finance** needs no API key. The backend calls the public chart endpoint
(`query2.finance.yahoo.com`, falling back to `query1`) at startup and caches the
daily bars in SQLite; it then appends at most one completed session per
`MARKET_DATA_REFRESH_HOURS`. Live mode uses the same endpoint for quotes. HTTP
429 (rate limit) and 5xx responses are retried with exponential backoff and
jitter (three attempts per host, honouring `Retry-After`) before the service
falls back to the cached dataset or another host. If Yahoo is unreachable on a
cold start and `MARKET_DATA_SOURCE=yahoo`, the service falls back to synthetic
sample prices and the dashboard labels them.

**CORS:** set `CORS_ORIGINS` to the static site's origin (including `https://`,
no path or trailing slash) and restart the service. Multiple origins are
comma-separated, so production and a preview domain can both be allowed. If the
dashboard shows a CORS error, compare the browser's `Origin` header with the
configured value exactly. Websockets are not subject to CORS; the dashboard
connects to `wss://<backend-host>/ws/market`.

**Persistence:** Render's free instances have an ephemeral filesystem, so the
SQLite cache, portfolios and trade history reset on restart or redeploy (prices
are simply downloaded again). For a durable competition, attach a Render disk
and set `DB_PATH` to a file on it, for example `/var/data/simulation.db`.
Free instances also spin down after idle time; a cold start re-imports market
data and resets the competition, so use a paid instance or a disk if that
matters.

### Frontend on a static host

The dashboard is a static Vite build. Set both variables in the host's build
environment (or a local `.env.production.local`), then build and publish
`frontend/dist`:

```bash
cd frontend
npm ci
VITE_API_BASE=https://your-api.onrender.com \
VITE_WS_URL=wss://your-api.onrender.com/ws/market \
npm run build
```

| Variable | Example | Purpose |
| --- | --- | --- |
| `VITE_API_BASE` | `https://ai-market-simulator-api.onrender.com` | Backend base URL, no trailing slash. |
| `VITE_WS_URL` | `wss://ai-market-simulator-api.onrender.com/ws/market` | Websocket endpoint; use `wss://` when the dashboard is served over HTTPS. |

Both are **build-time** values baked into the bundle; rebuild and redeploy the
static site after changing them. `frontend/.env.example` documents the pair.
Without them the app calls same-origin `/api` and `/ws` (the Vite dev proxy
handles this locally).

Host settings:

- Build command: `npm ci && npm run build`
- Publish directory: `dist`
- SPA rewrite: all paths to `/index.html` (the dashboard uses tabs, not routes,
  but the rewrite keeps refresh/deep links safe)

The included `render.yaml` defines this as the `ai-market-simulator-dashboard`
static service; Netlify, Vercel, Cloudflare Pages or S3/CloudFront work the same
way. After the static URL is known, add it to the backend's `CORS_ORIGINS` and
redeploy the backend.

## Deliberately not built yet

- Intraday charts, a date-range picker, and exchange-grade realtime quotes
  (live mode polls once a minute; replay shows daily closes).
- A real historical news feed: headlines are deterministic simulated sentiment.
- Trained ML models, news NLP, and prediction accuracy/F1 evaluation.
- Auth, multiple users, and per-user portfolios — the manual order endpoint is
  unauthenticated, so treat a public deployment as a demo only.
- Partial fills, limit orders, order cancellation, margin calls, dividends.
