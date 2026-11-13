# AI Market Simulator — Complete Feature and Function Reference

A paper-trading competition between three independent AI portfolios and one
manual portfolio. Each account starts with **$10,000**. The simulator either
replays roughly one year of real daily Yahoo Finance bars or follows live Yahoo
Finance quotes during the US session.

Everything is simulated: no real money, no brokerage connection, and no real
news feed. Headlines are generated locally. Market prices are real Yahoo
Finance data (or deterministic sample data when Yahoo is unavailable).

> This is a demo, not investment advice. The manual order endpoint is
> unauthenticated, so do not expose a deployment as a real trading service.

For a fictionalized, day-by-day account of the design, build and debugging
process, see the [build journal](docs/BUILD_JOURNAL.md).

---

## Table of contents

1. [What is in the project](#1-what-is-in-the-project)
2. [Quick start](#2-quick-start)
3. [The screen, control by control](#3-the-screen-control-by-control)
   - [Header and clock](#31-header-and-clock)
   - [Tabs](#32-tabs)
   - [Forecasts](#33-forecasts-tab)
   - [Leaderboard](#34-leaderboard-tab)
   - [Markets](#35-markets-tab)
   - [Trading](#36-trading-tab)
   - [Activity](#37-activity-tab)
   - [Loading, errors and reconnects](#38-loading-errors-and-reconnects)
4. [Replay and live modes](#4-replay-and-live-modes)
5. [AI agents and forecasts](#5-ai-agents-and-forecasts)
6. [The trading engine](#6-the-trading-engine)
7. [Market data and news](#7-market-data-and-news)
8. [Backend architecture and function reference](#8-backend-architecture-and-function-reference)
9. [API reference](#9-api-reference)
10. [WebSocket reference](#10-websocket-reference)
11. [Database reference](#11-database-reference)
12. [Frontend architecture and function reference](#12-frontend-architecture-and-function-reference)
13. [Configuration](#13-configuration)
14. [Deployment](#14-deployment)
15. [Tests](#15-tests)
16. [Troubleshooting](#16-troubleshooting)
17. [Deliberate limitations](#17-deliberate-limitations)
18. [Glossary](#18-glossary)

---

## 1. What is in the project

- **Three AI accounts**
  - **Price AI** — technical trend and momentum.
  - **News AI** — simulated headline sentiment.
  - **Combined AI** — 60% price signal, 40% news signal.
- **One manual account** — you trade it with Buy, Sell, Short and Cover.
- **Replay mode** — walks cached daily bars from Yahoo Finance. One bar is one
  completed trading day. Default history is one year (about 251 sessions).
- **Live mode** — polls real quotes every 60 seconds during the US session,
  keeps one forming daily bar per session, and lets agents re-evaluate every
  five minutes.
- **Forecasts** — each AI records its **top five** expected moves for the
  current decision, including expected percent, share price and expected
  dollar move per share.
- **Leaderboard** — ranks all four accounts by total return with max drawdown
  and trade counts.
- **Markets** — selectable ticker list, daily line chart, OHLC, volume and
  SMA 5 / SMA 20.
- **Trading** — manual order ticket, positions, recent orders and account
  summary.
- **Activity** — global fills and order history.
- **REST API + WebSocket** — all dashboard data is available programmatically.
- **SQLite persistence** — market cache, accounts, orders, fills, predictions
  and equity snapshots.

### Project layout

```text
.
├── backend/
│   ├── app/
│   │   ├── ai/            strategies, signals and forecast estimates
│   │   ├── api/           FastAPI route modules
│   │   ├── competition/   agent runner, rankings and metrics
│   │   ├── database/      SQLite schema and repositories
│   │   ├── market/        Yahoo daily/live data, news, data helpers
│   │   ├── services/      replay/live clock and pub/sub
│   │   ├── trading/       order manager, exchange, accounting, risk
│   │   ├── config.py      runtime settings and defaults
│   │   └── main.py        FastAPI app, CORS, health and WebSocket
│   ├── tests/             accounting, replay, API, data and forecast tests
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/
│   ├── src/
│   │   ├── api/           REST client and WebSocket URL
│   │   ├── components/    every visible panel and table
│   │   ├── hooks/         WebSocket/polling stream
│   │   ├── lib/           number and date formatting
│   │   ├── App.tsx        header, tabs and page switching
│   │   └── types.ts       shared frontend types
│   ├── public/
│   └── package.json
├── render.yaml            optional Render blueprint
└── README.md
```

---

## 2. Quick start

### Backend

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

- REST API: `http://localhost:8000`
- Interactive Swagger docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/health`
- WebSocket: `ws://localhost:8000/ws/market`

The first start downloads daily Yahoo Finance bars and stores them in SQLite.
If Yahoo cannot be reached, the backend falls back to deterministic synthetic
sample prices. With `SIM_AUTOSTART=0` the replay boots paused; press **Start**.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite serves `http://localhost:3000` and proxies `/api` and `/ws` to port 8000.
Open the page and use the tabs. The default tab is **Leaderboard**.

For a separate backend:

```bash
VITE_API_BASE=https://your-api.onrender.com \
VITE_WS_URL=wss://your-api.onrender.com/ws/market \
npm run build
```

Both values are baked into the bundle at build time. Rebuild after changing
them.

### Tests

```bash
cd backend
. .venv/bin/activate
python -m pytest -q
```

At the time of writing this is **52 passing tests**.

---

## 3. The screen, control by control

### 3.1 Header and clock

The header is always visible above the tabs.

| Element | What it does |
| --- | --- |
| **Market Simulator / AI paper trading** | Brand label. It is not a link. |
| **Clock date** | The simulation date: the current replay session, or the latest live session date. Format: `Feb 19, 2026`. |
| **Clock status** | `Running`, `Paused`, `Complete`, `Live · market open`, or `Live · market closed`. |
| **Replay button** | Switches to replay mode. Disabled while an action is in flight. Switching modes resets all four portfolios and their histories. |
| **Live button** | Switches to live mode and immediately performs an initial quote poll. Disabled while busy. Also resets all portfolios. |
| **1× / 5× / 10× / 30×** | Replay speed. Hidden in live mode. Each speed is one replay bar (one trading day) per `1 / speed` seconds, so 1× = one day per second and 30× = thirty days per second. |
| **Start** | Starts or resumes a paused replay. Disabled while busy. If the replay is complete, the button label is **Restart**; pressing it resets the replay and starts from bar 0. |
| **Pause** | Pauses a running replay. Hidden in live mode. |
| **Reset** | Resets the current mode: all accounts go back to $10,000, and orders, trades, predictions and equity snapshots are deleted. In replay it goes to the first bar and pauses; in live it goes to the latest bar and continues running. |
| **Progress bar** | Thin line under the header showing replay progress. Hidden in live mode. It is decorative and not interactive. |

Header controls are disabled while an action request is running. The buttons do
not open dialogs; Reset acts immediately.

### 3.2 Tabs

Tabs switch client-side panels without changing the URL. The leftmost tab is
**Forecasts**; the default selected tab is **Leaderboard**.

| Tab | Contents |
| --- | --- |
| **Forecasts** | The largest expected move across all AIs, plus each AI's ranked top five. |
| **Leaderboard** | Ranked accounts, quote list and your account summary. |
| **Markets** | Ticker selector, price chart, OHLC/volume and moving averages. |
| **Trading** | Manual order ticket, account values, positions and recent orders. |
| **Activity** | Latest fills and latest orders across all accounts. |

Tabs are buttons, not links. There are no per-tab URLs, browser-history entries
or deep links.

### 3.3 Forecasts tab

The Forecasts tab answers: **“What does each AI think its five biggest wins
are right now?”**

#### Biggest expected win hero

At the top, the panel titled **Biggest expected win** shows the single forecast
with the largest absolute expected percentage across every AI.

- Large arrow: `↑` for UP, `↓` for DOWN, `→` for FLAT.
- Expected percentage, with two decimals.
- Ticker and an agent tag.
- A sentence such as “Price AI expects a rise of about 6.84% over the next five
  sessions, a move of +$47.31 per share.”
- For a DOWN call it adds: “A short would target that move.”
- Confidence as a percentage.
- The agent's rationale (for example `SMA5 704.33 vs SMA20 656.43; 10-bar
  momentum +14.50%`).
- The date of the call.

The hero does not contain buttons.

#### Per-AI panels

Below the hero are three panels, one per AI. Each is ordered by absolute
expected percentage, largest first, and shows up to five calls.

Each row contains:

| Column/line | Meaning |
| --- | --- |
| Rank | `1` to `5`, largest absolute expected move first. |
| Ticker | The stock symbol. |
| Rise/drop/flat | Direction label derived from the sign of the expected move. |
| Expected percentage | Signed estimate, e.g. `+6.84%` or `-4.98%`. Green for positive, red for negative. |
| Price per share | The price used for the estimate: the current replay or live price. |
| Estimated dollar move | `price × expected_pct / 100`, signed, labelled `est.`. This is the expected change in the value of one share, not a position-sized P&L. |

If an agent has fewer than five non-zero estimates, it shows fewer rows. If no
agent has recorded a call yet, the tab shows:

> No calls yet. Start the replay and the AIs will rank their five biggest
> expected moves before each trading day's orders.

Forecasts are recorded before the agent's order intents are submitted. In
replay, the whole batch is replaced once per bar. In live mode, it is replaced
on each agent decision while the market is open. A down call is a candidate
short, not a guaranteed win. The percentage and dollar figures are model
estimates based on signal strength and recent volatility.

### 3.4 Leaderboard tab

The Leaderboard panel ranks every account by total return.

| Column | Meaning |
| --- | --- |
| `#` | Rank. Ties are broken by lower maximum drawdown. |
| Account | Agent name, or **You** with a `manual` tag. |
| Equity | Cash plus the mark-to-market value of all positions. |
| Return | Total return percentage from the $10,000 starting balance. |
| Max DD | Maximum peak-to-trough equity drawdown, shown as a negative percentage. |
| Trades | Total filled trades. |

No column is clickable and the table cannot be sorted by the user. The ranking
always comes from the backend.

The right column contains:

- **Markets** — every universe ticker with its latest price and daily change.
  These rows are plain text, not buttons.
- **Your account** — manual account equity, cash and number of open positions.

The Overview/Leaderboard tab does not show win rate, fees, borrow costs or
individual positions; those values are available through the API.

### 3.5 Markets tab

#### Ticker list

The left panel lists all eight tickers. Each row is a **button**:

- Ticker symbol.
- Latest price.
- Daily change percentage.

Clicking a row selects that ticker. The selected row is highlighted. No ticker
is added or removed by the user.

#### Quote header

For the selected ticker:

- Ticker and latest price.
- Change percentage.
- A caption with the quote date and `close`, `live`, or `last close` depending
  on mode and market state.

#### Price chart

The chart is a responsive SVG line chart of closing prices, not candlesticks.

- Up to 240 bars are requested from `/api/market/history/{ticker}?limit=240`.
- The line is green when the last close is at or above the first close, red
  otherwise.
- A translucent area fill follows the line.
- Four horizontal grid lines are labelled with prices on the right.
- The last price has a dashed horizontal marker and a dot.
- The first and last dates are printed under the chart.
- The chart has no zoom, pan, crosshair, tooltip or range picker.
- With fewer than two bars it shows “Collecting daily bars…”.

The chart refreshes when the selected ticker changes, every two replay bars,
and on each live poll timestamp.

#### Quote statistics

| Stat | Source |
| --- | --- |
| Open | Current bar open. |
| High | Current bar high. |
| Low | Current bar low. |
| Volume | Current bar volume, with thousands separators. |
| SMA 5 | Average of the last five closes, or `—`. |
| SMA 20 | Average of the last twenty closes, or `—`. |

Below the stats is a data note describing the data source and, in replay, the
last bar date. In live mode the note describes Yahoo polling and simulated
headlines.

### 3.6 Trading tab

#### Trade ticket

- **Ticker** — a dropdown of the eight universe tickers.
- **Shares** — a number input. Minimum 1, integer step. Default is 5.
- **Buy** — opens or adds to a long position.
- **Sell** — reduces an existing long. It cannot open a short.
- **Short** — opens or adds to a short position.
- **Cover** — reduces an existing short. It cannot open a long.

All four order buttons are disabled while an order is being submitted and when
the replay is complete. The button that is submitting changes its label to `…`.

The helper text under the fields shows the selected price (`live` or
`last close`) and the fill expectation:

- Replay: “fills at the next day's open”.
- Live and market open: “fills on the next quote”.
- Live and market closed: “queued until the market opens”.

After submission a notice shows the server message. The app refreshes the
snapshot immediately and again after 700 ms. A negative or non-numeric share
count shows “Enter a positive number of shares.”

When the replay is complete, the ticket is disabled and says “Replay finished.
Reset to trade again.”

#### Account panel

Shows the manual account's equity, cash, positions value and total return.
Values are read-only.

#### Positions table

| Column | Meaning |
| --- | --- |
| Ticker | Stock symbol. |
| Shares | Signed quantity: `+` long, `-` short. |
| Avg | Average entry price. |
| Last | Current mark price. |
| P&L | Unrealized profit/loss in dollars, green or red. |

It shows “No open positions.” when empty. This table has no close button; use
the Sell or Cover buttons in the ticket.

#### Recent orders table

Shows the six most recent manual orders:

- Time, side, ticker, shares, status and fill price.
- Status is `PENDING`, `FILLED`, `REJECTED` or `CANCELLED`.
- Rejected orders show a shortened rejection reason.
- Fill is `—` until the order fills.

#### What each order means

| Side | Opens/closes | Cash effect | Constraint |
| --- | --- | --- | --- |
| BUY | Opens or adds long | Cash decreases by notional + fee | No existing short in that ticker |
| SELL | Reduces long | Cash increases by notional − fee | Cannot exceed the long quantity |
| SHORT | Opens or adds short | Cash increases by notional − fee | No existing long in that ticker |
| COVER | Reduces short | Cash decreases by notional + fee | Cannot exceed the short quantity |

Orders are **market orders**. They are queued as `PENDING` and filled by the
simulation loop at the next eligible price. A queued order is validated again
at fill time; it can be rejected if cash, position limits or prices have
changed.

### 3.7 Activity tab

The Activity tab has two panels.

#### Fills

The twelve most recent actual fills across every portfolio:

- Time, account, side, ticker, shares, price and realized P&L.
- Realized P&L is `—` for opening trades and a signed dollar value for closing
  trades.

#### Orders

The twelve most recent orders across every portfolio:

- Time, account, side, ticker, shares, status and fill price.
- Rejected orders show the reason prefix.

The Activity tab refreshes when the replay bar changes (checked in two-bar
buckets). It does not have filters, pagination, export or a manual refresh
button.

### 3.8 Loading, errors and reconnects

- Before the first snapshot arrives, the page shows **Connecting…**.
- If the backend cannot be reached and there is no snapshot yet, a red error
  says “Cannot reach the backend.” with the HTTP/network error.
- A failed header/order action shows the server's error message in a red banner
  above the active tab.
- The frontend connects to `/ws/market`. If the socket closes, it retries every
  2.5 seconds.
- While the socket is unavailable, the app polls the REST endpoints every three
  seconds.
- Malformed WebSocket frames are ignored so a bad frame does not tear down the
  stream.
- Tab switches are instant; there is no page reload.

---

## 4. Replay and live modes

### Replay mode

- Uses completed daily OHLCV bars only. The partial current day is excluded.
- One bar equals one trading day. The default Yahoo range is one year (usually
  251 bars).
- The clock starts at bar 0. With `SIM_AUTOSTART=1` it runs immediately;
  otherwise it starts paused.
- Every tick:
  1. Fills pending orders at the next bar's **open**.
  2. Advances the cursor and marks positions at the new closes.
  3. Accrues short borrow fees when the session date changes.
  4. Runs agent decisions when the bar index matches the decision cadence
     (every bar in the default configuration).
  5. Records equity snapshots and broadcasts a new snapshot.
- At the final bar, pending orders are cancelled with `replay_finished`, the
  status becomes `COMPLETED`, and no further decisions are made.
- **Start** resumes; **Pause** stops advancing; **Restart** after completion
  resets and starts again.
- Changing speed affects how quickly bars advance; it does not change fills or
  decisions.

### Live mode

- The backend polls Yahoo Finance every `LIVE_POLL_SECONDS` (60 by default)
  while the simulation is running.
- During the regular US session it maintains one forming daily bar for today:
  open, high, low, latest price and cumulative volume.
- Pending orders fill at the latest quote on the next poll.
- Agents re-evaluate every `LIVE_DECISION_SECONDS` (300 by default) and when a
  new live session is first created.
- The header shows **Live · market open** or **Live · market closed**. Outside
  the regular session, weekends and holidays, prices are the last known prints
  and no session bar is created or filled.
- The Start/Pause and speed controls are hidden in live mode; the simulation is
  running while the mode is active. **Reset** resets accounts and clears
  history, then continues running.
- In live mode the data note explains the poll interval and that headlines are
  simulated.
- A live poll failure is recorded in the live state and shown through the API;
  the UI keeps the last known prices.

### Switching modes

Switching from replay to live (or back):

1. Cancels every pending order with `mode_switch`.
2. Resets all four accounts to $10,000 and deletes positions, trades, orders,
   predictions and equity snapshots.
3. Switches the clock.
4. On the way back to replay, deletes a still-forming live session so it cannot
   leak into history.
5. Replay: cursor goes to bar 0 and pauses. Live: cursor goes to the latest bar
   and runs, then performs an initial quote poll.

Mode switches are deliberately destructive: results from replay and live are
not mixed.

### Speeds

| Speed | One trading day per |
| --- | --- |
| 1× | 1 second |
| 5× | 0.2 seconds |
| 10× | 0.1 seconds |
| 30× | about 0.033 seconds |

The speed options come from the backend and are fixed at `(1, 5, 10, 30)`.

---

## 5. AI agents and forecasts

### The shared agent lifecycle

All agents extend `BaseAgent` and follow the same rules:

1. Receive a read-only `MarketContext` containing the visible prices, bars, news
   and current bar index.
2. `evaluate()` returns one `Signal` per ticker with a score roughly in
   `[-1, 1]`, a confidence and a human-readable rationale.
3. Signals are filtered to tickers with a current price and sorted by score
   descending.
4. The agent records its **top five** expected moves.
5. The agent converts signals into `OrderIntent`s using fixed entry/exit
   thresholds and position sizing.
6. The order manager, not the agent, validates and queues every intent.

Agents never change cash, positions or order status directly.

### Signal scoring

The shared technical score uses:

- `SMA5` and `SMA20` of closing prices.
- 10-bar percentage momentum.
- `trend = tanh((SMA5 / SMA20 - 1) × 120)`.
- `momentum_component = tanh(10-bar return × 25)`.
- `score = 0.6 × trend + 0.4 × momentum_component`, clamped to `[-1, 1]`.

It needs at least 20 closes (and 11 for momentum). When there is not enough
history it returns no signal.

### History windows

The models never see the future. Each one reads a fixed window ending at the
current replay or live bar:

| Input | Lookback |
| --- | --- |
| Price trend | 5-session and 20-session moving averages |
| Price momentum | 10 sessions |
| News sentiment | Last 5 sessions |
| Realized volatility | Last 20 sessions |
| Forecast horizon | Next 5 sessions |
| Bars loaded into the context | Up to 120 |

The context loads more bars than the models use so the history endpoint and
debugging have room; the scoring windows above are the actual limits. The
Forecasts tab shows these lookbacks above the calls, and
`overview.forecast_meta` exposes the same values to API clients.

### The three strategies

| Agent | Signal | Entry threshold | Exit threshold | Max entries | Long target | Short target |
| --- | --- | --- | --- | --- | --- | --- |
| **Price AI** | 60% SMA5/SMA20 trend + 40% 10-bar momentum | 0.30 | 0.05 | 2 | 16% of equity | 10% of equity |
| **News AI** | Average simulated sentiment over the last 5 bars, multiplied by 1.5 | 0.22 | 0.02 | 2 | 16% of equity | 10% of equity |
| **Combined AI** | 60% price score + 40% news component | 0.26 | 0.03 | 3 | 13% of equity | 8% of equity |

The rationale strings shown in the Forecasts tab come directly from these
calculations, e.g. `price -0.90 + news -0.12 (18 headlines) -> -0.59`.

### Entry, exit and sizing rules

For each signal, in score order:

- If holding a **long** and `score <= exit_threshold`: emit `SELL` for the whole
  long.
- If holding a **short** and `score >= -exit_threshold`: emit `COVER` for the
  whole short.
- If already holding the ticker, skip adding.
- Stop after `max_entries` new positions per decision.
- If `score >= entry_threshold`: buy
  `min(equity × target_position_pct, cash × 0.95)` worth, rounded down to whole
  shares.
- If `score <= -entry_threshold`: short `equity × target_short_pct` worth,
  rounded down to whole shares.
- Orders that would exceed the engine's risk limits are rejected later by the
  exchange.

### Forecast estimates

Each recorded call contains:

- **Direction** — `UP` if the expected percentage is positive, `DOWN` if
  negative, otherwise `FLAT` (flat is filtered out of the recorded top five).
- **Expected percent** — the model's estimated five-session move.
- **Price** — current replay or live price when the call was recorded.
- **Expected dollars per share** — `price × expected_pct / 100`, computed by the
  API.
- **Confidence** — `clamp(0.5 + abs(score) × 0.45, 0.5, 0.95)`.
- **Rationale**, **simulation time**, **bar index**.

The expected-move formula is:

```text
expected_pct = score × realized_volatility_20d × sqrt(5) × 100
```

- `realized_volatility_20d` is the standard deviation of the last 20 daily
  returns.
- The result is rounded to two decimals and clamped to **±15%**.
- If there is not enough history for volatility, it falls back to
  `score × 3`, also clamped to ±15%.

A **down** estimate is not “the AI loses money”; it is a candidate short. The
ranking is by absolute expected percentage, so a large drop can rank above a
large rise.

### When forecasts are recorded

- **Replay:** every agent decision (normally every bar) records a new top five.
  Rows are replaced for that agent and bar, so old ranks do not accumulate.
- **Live:** on each agent decision (initial live session creation and then every
  `LIVE_DECISION_SECONDS`) while the market is open. Between decisions the tab
  shows the latest batch.
- Forecasts are dated with the simulation time and are only visible through
  data at or before the current cursor.
- Agents need enough history; early bars can produce fewer than five calls.
- Switching mode or resetting clears all forecasts.

### Running a prediction immediately

The **Predict now** button on the Forecasts tab calls
`POST /api/market/forecasts/refresh`. It runs all three agents against the
latest visible bar and replaces that bar's batch, without submitting orders or
waiting for the next replay tick or live decision interval. It works while
paused and after hours, but it cannot invent bars: with too little visible
history it returns fewer calls, and after hours it uses the last available
session. The response includes `forecasts`, `forecast_meta`, `sim_time` and
`generated_at`.

The Forecasts tab shows the latest batch per agent, not a full forecast history.
History is available from `/api/predictions` and
`/api/agents/{id}/predictions`.

---

## 6. The trading engine

### Orders versus trades

- An **order** is an intent. It can be pending, filled, rejected or cancelled.
- A **trade** is an immutable fill created by the exchange.
- Manual and AI orders use the same order manager and exchange.

### Order lifecycle

1. `OrderManager.submit()` validates side, ticker, quantity and portfolio, then
   inserts a `PENDING` order.
2. On the next tick (replay) or next live poll, `fill_pending()` sees the order.
3. The exchange validates the order against cash, positions and risk limits
   using the actual fill price.
4. A valid order becomes `FILLED`, mutates the portfolio, and creates a trade.
5. An invalid order becomes `REJECTED` with a reason. It never mutates the
   portfolio.

Replay fills at the next session's **open**. Live fills at the **latest quote**
on the poll after submission. Manual and AI orders share this behavior.

### Sides

| Side | Meaning |
| --- | --- |
| BUY | Open or add a long. Cannot be used while short the same ticker. |
| SELL | Reduce a long. Cannot open a short. |
| SHORT | Open or add a short. Cannot be used while long the same ticker. |
| COVER | Reduce a short. Cannot open a long. |

Quantities are positive integers; the sign is carried by the position, not the
order quantity.

### Risk checks

All checks use the fill price and current portfolio equity:

- Side must be one of BUY, SELL, SHORT, COVER.
- Quantity must be positive.
- A price must exist.
- Equity must be positive.
- BUY:
  - No existing short in the ticker.
  - Cash must cover notional plus fee.
  - Order notional cannot exceed **25% of equity**.
  - Resulting long market value cannot exceed **25% of equity**.
- SELL:
  - Must have a long position.
  - Cannot sell more than the long quantity.
- SHORT:
  - No existing long in the ticker.
  - Order notional cannot exceed **25% of equity**.
  - Resulting short market value cannot exceed **20% of equity**.
  - Total short exposure across the portfolio cannot exceed **50% of equity**.
- COVER:
  - Must have a short position.
  - Cannot cover more than the short quantity.
  - Cash must cover notional plus fee.

Rejection reasons include `invalid_side`, `invalid_quantity`, `no_price`,
`account_depleted`, `conflicting_position`, `insufficient_buying_power`,
`position_limit`, `no_long_position`, `insufficient_long_position`,
`short_position_limit`, `short_exposure_limit`, `no_short_position`,
`insufficient_short_position`, `order_size_limit`, `unknown_ticker` and
`unknown_portfolio`.

### Costs

- **Transaction fee:** 5 basis points (0.05%) of notional, per side, on both
  buys/covers and sells/shorts.
- **Short borrow:** 8% annualized on short market value, accrued once per
  simulated session. Live session creation also accrues it.
- Fees reduce cash and are recorded on the trade.
- Borrow fees are tracked per position and per portfolio and reduce cash.

### Accounting identities

```text
equity = starting_balance + realized_pnl + unrealized_pnl
         - fees_paid - borrow_fees
```

- Long: cash pays notional + fee, position is positive.
- Short: cash receives notional − fee, position is negative (a liability).
- SELL realized P&L: `(fill_price − average_entry) × quantity`.
- COVER realized P&L: `(average_entry − fill_price) × quantity`.
- Average entry is blended when adding to a position.
- When a position returns to zero, its average entry resets to 0.
- Portfolio values mark open positions to the latest available price.

### Equity curve and snapshots

At the end of each replay tick (and each live session update), the engine stores
one `portfolio_snapshots` row per portfolio with cash, positions value and
equity. These snapshots power maximum drawdown and the equity curve returned by
the portfolio APIs.

---

## 7. Market data and news

### Daily replay data

- Source: Yahoo Finance's public chart endpoint, daily interval.
- Default range: `1y`.
- Only completed sessions are used. While the US market is open, today's partial
  session is dropped.
- Tickers are downloaded concurrently, aligned on one shared calendar, and
  missing sessions are forward-filled with the previous close (volume 0).
- A dataset is refused if it has fewer than 60 sessions or if any ticker is
  missing more than half the calendar.
- Bars are stored in SQLite with a shared `bar_index` per session date.
- The `data_cache` row records source, fetch time, last bar date and bar count.

### Data refresh

- On startup, cached Yahoo daily bars are reused if they are younger than
  `MARKET_DATA_REFRESH_HOURS` (24 by default).
- If the cache is stale, the backend downloads again and appends newly completed
  sessions. It does not duplicate existing sessions.
- The background loop checks refresh eligibility every 15 minutes.
- If Yahoo fails during a refresh, the cached dataset is retained and marked
  stale. If there is no cache on a cold start, synthetic sample data is used.

### Synthetic fallback

- Deterministic seeded OHLCV bars for the eight tickers.
- Used when `MARKET_DATA_SOURCE=synthetic` or when Yahoo is unreachable on a cold
  start.
- The dashboard label becomes **Sample data**, and the data note says synthetic
  sample prices are in use.
- Synthetic mode is intended for offline development and tests, not realistic
  results.

### Live quotes

- Yahoo chart endpoint with `range=1d&interval=1m&includePrePost=false`.
- One quote per ticker: latest price, previous close, day open/high/low, volume
  and market time.
- Market open means a weekday inside 09:30–16:00 New York time and a quote no
  more than 30 minutes old.
- Quotes are fetched concurrently with a 10-second timeout.
- One failed ticker does not fail the whole poll; the error is reported in the
  live state.
- Outside the session the latest trade is typically the previous close; no new
  forming bar is created.

### Yahoo retries

The shared HTTP helper retries HTTP 429, 500, 502, 503 and 504 up to three
attempts per host.

- Exponential backoff starts at 0.5 seconds.
- Jitter of up to 10% (capped at 0.25 seconds) is added.
- The delay is capped at 8 seconds.
- A numeric `Retry-After` header is honored if longer.
- Other HTTP errors are raised immediately.
- Two hosts are tried: `query2.finance.yahoo.com` then
  `query1.finance.yahoo.com`.

### News

- News is **simulated**, not downloaded.
- Each session receives one market-wide headline and one to three headlines per
  ticker.
- Headline mood is deterministic from the session date and configured seed.
- Sentiment is in `[-1, 1]`; neutral headlines are damped.
- Every item carries the bar index at which it becomes visible, so agents never
  see future headlines.
- Headline sources are fictional: MarketWire, FinPress, StreetScope, TapeDaily,
  CapitalPost.
- The News AI uses a rolling five-session window. Market-wide headlines count at
  35% weight for a specific ticker.

### Indices

The API also returns synthetic index levels (`SPX` and `IXIC`) derived from the
universe's weighted daily change. They are present in the overview/snapshot
payloads but are not currently rendered in a dedicated dashboard panel.

---

## 8. Backend architecture and function reference

This section lists the important classes and functions by module. Private
helpers are included where they carry behavior worth knowing.

### Entry point and configuration

| Module | Item | Purpose |
| --- | --- | --- |
| `app/main.py` | `cors_origins()` | Parses `CORS_ORIGINS`, strips whitespace/trailing slashes, defaults to `*`. |
| | `create_app(settings)` | Builds the FastAPI app, lifespan, SQLite, repository, event manager, engine, CORS, routers, health, root and WebSocket. |
| | `lifespan(app)` | Opens the database, seeds accounts, starts the simulation loop, closes on shutdown. |
| | `health()` | `GET /api/health`: service status, simulation payload and public settings. |
| | `root()` | `GET /`: service name, docs path and WebSocket path. |
| | `market_socket(websocket)` | Accepts `/ws/market`, subscribes to events, sends the initial snapshot, forwards frames. |
| `app/config.py` | `DEFAULT_UNIVERSE` | AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, META, AMD. |
| | `SPEED_OPTIONS` | `(1, 5, 10, 30)`. |
| | `_default_db_path()` | Defaults to `backend/data/simulation.db`. |
| | `_env_float(name, default)` | Safe float environment parsing. |
| | `Settings` | Frozen dataclass for capital, costs, limits, data, replay and live settings. |
| | `Settings.as_public_dict()` | Non-secret settings exposed by `/api/health`. |

### Simulation clock (`app/services/simulation_clock.py`)

| Function | Purpose |
| --- | --- |
| `SimulationEngine.__init__` | Creates exchange, order manager, competition manager, empty timeline, live state and lock. |
| `initialize()` | Loads/replaces data, seeds accounts, loads agents, restores or resets the saved run. |
| `_ensure_market_data()` | Reuses cache, refreshes stale Yahoo data, or seeds synthetic data; returns whether the dataset changed. |
| `_seed_synthetic()` | Creates deterministic sample bars/news and marks the source as synthetic. |
| `_replace_dataset(dataset)` | Replaces all bars/news with a fresh Yahoo dataset. |
| `_append_dataset(dataset)` | Appends only new completed sessions; returns the count. |
| `_store_cache(dataset)` | Writes the data-cache metadata row. |
| `_set_data_info_from_cache(cache, summary, stale=False)` | Builds the dashboard's data-source description. |
| `_cache_age_hours(cache)` | Age of the cached dataset in hours. |
| `data_payload()` | Public data-source information, including live polling notes. |
| `refresh_data_if_due()` | Refreshes stale Yahoo data at most once per configured window. |
| `play()`, `pause()`, `reset()` | Clock controls. `play()` restarts a completed replay. |
| `switch_mode(mode)` / `_switch_mode(mode)` | Validates and executes replay/live switching and destructive reset. |
| `set_speed(speed)` | Stores a validated replay speed. |
| `interval_seconds` | Seconds between replay ticks: `bar_interval_seconds / speed`. |
| `tick()` | Advances one replay bar: fills pending orders, marks prices, accrues borrow, runs decisions, snapshots and persists. |
| `live_tick()` / `_live_tick()` | Polls quotes, updates the live bar, fills pending orders and runs decisions on the live cadence. |
| `_ensure_live_session(snapshot)` | Creates or updates today's forming live bar and its simulated news. |
| `_reload_timeline()` | Reloads bars/index and recalculates the live cursor. |
| `_complete()` | Marks replay complete and cancels pending orders. |
| `run_loop()` | Async background loop for replay ticks or live polls, plus periodic data refresh. |
| `shutdown()` | Stops the background task. |
| `status_payload()` | Status, mode, speed, bar index, dates, progress, decision cadence and live state. |
| `reference_prices()` | Previous session's closes (basis for daily change). |
| `quotes_payload()` | Quote rows for every universe ticker at the current bar. |
| `forecasts_payload()` | Groups the latest top-five calls per AI, adds `expected_usd`, and returns them in agent order. |
| `snapshot()` | Full dashboard frame: simulation, quotes, indices, forecasts, leaderboard, manual account, data info and server time. |
| `_publish()` | Sends a snapshot to WebSocket subscribers. |
| `_take_snapshots(sim_time)` | Stores one equity snapshot per portfolio. |
| `_persist()` | Saves clock status to `simulation_runs`. |

### Repository (`app/database/repositories.py`)

| Function | Purpose |
| --- | --- |
| `seed_accounts(settings, now)` | Creates the three agents and four portfolios once. |
| `get_simulation()` / `upsert_simulation(...)` | Load/save the single simulation state row. |
| `list_agents()` / `get_agent(id)` | Agent records. |
| `list_portfolios()` / `get_portfolio(id)` / `get_portfolio_by_agent(agent_id)` / `get_manual_portfolio()` | Portfolio lookups. |
| `update_cash(portfolio_id, cash, borrow_fees)` | Cash/borrow persistence. |
| `load_state(portfolio_id)` / `save_state(state)` | Convert between database rows and `PortfolioState`. |
| `list_positions(portfolio_id)` | Signed positions. |
| `insert_order(...)` | Queue a `PENDING` order. |
| `get_order(id)` / `list_orders(portfolio_id, limit)` / `list_pending_orders()` | Order queries. |
| `mark_order_filled(...)` | Mark filled, store fill price/fees/time. |
| `cancel_pending_orders(reason)` | Cancel all pending orders. |
| `mark_order_rejected(id, reason)` | Store a rejection reason. |
| `insert_trade(...)` / `list_trades(portfolio_id, limit)` | Immutable fills and history. |
| `insert_prediction(...)` | Record one prediction (used by tests/tools). |
| `replace_predictions(agent_id, rows)` | Delete one agent's calls for a bar and insert the new batch. |
| `latest_forecasts(bar_index, per_agent=5)` | Latest batch per agent, ordered by absolute expected move, limited per agent. |
| `latest_predictions(bar_index)` | One latest row per agent (legacy helper). |
| `list_predictions(agent_id, limit)` | Prediction history, newest/largest first. |
| `count_bars()` | Number of market bars. |
| `bulk_insert_bars(bars)` / `bulk_insert_news(items)` | Bulk imports. |
| `get_data_cache()` / `save_data_cache(...)` | Dataset metadata. |
| `market_summary()` | Bar count and date range. |
| `plan_new_sessions(session_dates)` | Assigns new bar indices. |
| `append_market_data(...)` | Appends bars, sessions and news. |
| `upsert_bars(bars)` | Update live forming bars. |
| `delete_session(session_date)` | Remove a forming live session. |
| `replace_market_data(bars, news)` | Replace the whole replay dataset. |
| `timeline()` / `last_bar_index()` | Bar index/session timeline. |
| `bars_at(index)` / `bar(ticker, index)` / `bars_for(ticker, up_to, limit)` / `bars_range(...)` | Price lookups. |
| `prices_at(index)` / `opens_at(index)` / `session_open_prices(date)` | Price maps. |
| `news_up_to(bar_index, ticker, limit)` | Clock-gated news. |
| `insert_snapshot(...)` / `snapshots(portfolio_id, limit)` / `latest_snapshot(id)` | Equity history. |
| `trade_stats(portfolio_id)` | Fees, wins, closed trades, realized P&L and trade counts. |
| `reset_trading()` | Deletes snapshots, trades, orders, predictions and positions. |
| `reset_accounts(settings, now)` | Restores cash/borrow and calls `reset_trading()`. |

### Trading engine modules

| Module | Item | Purpose |
| --- | --- | --- |
| `accounting.py` | `round_money` | Round to cents. |
| | `trade_fee(notional, fee_bps)` | Per-side transaction fee. |
| | `market_value(quantity, price)` | Signed market value. |
| | `unrealized_pnl(quantity, average_entry, price)` | Open P&L for long or short. |
| | `borrow_fee(quantity, price, annual_rate, days=1)` | Daily short borrow charge. |
| | `blended_entry(old_quantity, old_average, added, price)` | Weighted average entry. |
| `portfolio.py` | `Holding` | Ticker, signed quantity, average entry, realized P&L and borrow fees. |
| | `Holding.is_long` / `is_short` | Position-side helpers. |
| | `PortfolioState` | Cash, start balance, holdings and aggregate borrow fees. |
| | `holding`, `prices_with`, `positions_value`, `equity`, `gross_long_exposure`, `gross_short_exposure`, `position_value`, `unrealized_pnl`, `realized_pnl` | Portfolio calculations. |
| `risk_limits.py` | `SIDES` | BUY, SELL, SHORT, COVER. |
| | `OrderRejected` | Exception with machine reason and readable detail. |
| | `OrderCheck` | Side/ticker/quantity/fill price tuple. |
| | `validate_order(...)` | All cash, position, short-exposure and order-size checks. |
| | `_check_order_notional(...)` | 25% cap on orders that increase exposure. |
| `exchange.py` | `Exchange.execute_order(...)` | Validate, mutate cash/position, mark the order, insert a trade. |
| | `Exchange.accrue_borrow_fees(...)` | Charge short positions once per session. |
| | `Exchange.state_summary(...)` | Cash, positions value and equity summary. |
| `order_manager.py` | `OrderManager.submit(...)` | Validate and queue manual/AI orders. |
| | `OrderManager.fill_pending(...)` | Fill every pending order at the next price or reject it. |

### AI modules

| Module | Item | Purpose |
| --- | --- | --- |
| `base_agent.py` | `MarketContext` | Immutable prices, bars, news, sim time and bar index. |
| | `OrderIntent` | Ticker, side and quantity produced by an agent. |
| | `Signal` | Ticker, score, confidence and rationale. |
| | `BaseAgent.evaluate()` | Abstract strategy method. |
| | `BaseAgent.step()` | Evaluate, filter, sort, record forecasts, then produce intents. |
| | `BaseAgent.record_forecasts()` | Evaluate and record a fresh top five without producing intents. Used by manual prediction. |
| | `BaseAgent._record_predictions()` | Rank non-zero estimates by absolute move and replace the agent's top five for the bar. |
| | `BaseAgent._signals_to_intents()` | Entry/exit decisions and per-position sizing. |
| | `BaseAgent._shares_for()` | Floor a dollar budget to whole shares. |
| | `BaseAgent.position_snapshot()` | Cash, equity and realized P&L helper. |
| `price_agent.py` | `PriceAgent.evaluate()` | Technical score for every ticker with enough history. |
| `news_agent.py` | `NewsAgent.evaluate()` | Five-bar sentiment score per ticker. |
| `combined_agent.py` | `CombinedAgent.evaluate()` | 60/40 blend of price and news. |
| `features.py` | `sma`, `pct_return`, `realized_volatility` | Rolling statistics. |
| | `technical_score(bars)` | SMA/momentum score plus diagnostics. |
| | `expected_move_pct(bars, score, horizon=5)` | Volatility-scaled, clamped forecast. |
| | `sentiment_score(news, ticker, min_bar)` | Weighted average and latest headline. |
| | `clamp` | Bound a number. |
| `predictions.py` | `direction_for(score, threshold)` | Threshold-based UP/DOWN/FLAT helper. |
| | `confidence_for(score)` | 0.5–0.95 confidence mapping. |

### Competition modules

| Module | Item | Purpose |
| --- | --- | --- |
| `manager.py` | `CompetitionManager.__init__` | Holds repository, settings and order manager. |
| | `load_agents()` | Instantiates Price, News and Combined agents from seeded portfolios. |
| | `run_decisions(...)` | Builds context, calls every agent, submits intents, records orders. |
| | `agent_view(...)` | Combines agent metadata, portfolio view and latest prediction. |
| `leaderboard.py` | `build_portfolio_view(...)` | Positions, cash, equity, metrics, short exposure, optional equity curve. |
| | `build_leaderboard(...)` | Views for every portfolio, sorted by return then drawdown, with ranks. |
| `metrics.py` | `max_drawdown_pct` | Largest peak-to-trough decline. |
| | `win_rate_pct` | Wins / closed trades. |
| | `total_return_pct` | Equity / starting balance − 1. |
| | `portfolio_metrics(...)` | Assembles all account metrics. |

### Market data modules

| Module | Item | Purpose |
| --- | --- | --- |
| `data_provider.py` | `ReplayWindow` | Synthetic date/bars metadata. |
| | `next_business_day`, `session_dates`, `bar_times` | Calendar helpers. |
| | `generate_bars(...)` | Deterministic synthetic OHLCV generator. |
| | `index_levels(...)` | Synthetic SPX/IXIC levels from universe changes. |
| | `BASE_PRICES`, `BASE_VOLUME` | Synthetic starting prices/volumes. |
| `data_processor.py` | `clamp`, `quote_payload`, `moving_average` | Quote formatting and averages. |
| `yahoo_http.py` | `retry_delay(...)` | Exponential backoff with jitter/Retry-After. |
| | `request_json(...)` | JSON GET with retries for 429/5xx. |
| | `HOSTS`, `RETRYABLE_STATUS` | Yahoo hosts and retryable codes. |
| `yahoo_provider.py` | `DailyDataset` | Bars, tickers, fetch time, last date, interval/source. |
| | `last_completed_session()` | Newest completed US trading day. |
| | `_request`, `_ticker_days` | Fetch and convert one ticker's daily series. |
| | `fetch_daily_bars(...)` | Concurrent download, calendar alignment, validation. |
| `live_provider.py` | `LiveQuote` / `LiveSnapshot` | One quote / a complete poll. |
| | `market_hours_open(...)` | Weekday regular-session check. |
| | `parse_quote(...)` | Parse Yahoo chart metadata/series into a quote. |
| | `fetch_live_quotes(...)` | Concurrent polls, staleness and market-open decision. |
| `news_provider.py` | `generate_news_for_dates(...)` | Headlines aligned to real trading dates. |
| | `generate_news(...)` | Headlines aligned to synthetic bars. |

### API modules

| Module | Routes | Purpose |
| --- | --- | --- |
| `api/simulation.py` | `/api/simulation/*` | Status, mode, start, pause, reset, speed. |
| `api/market.py` | `/api/market/*` | Overview, quote, history, news. |
| `api/agents.py` | `/api/agents*` | Agent list/detail, portfolios, prediction history. |
| `api/portfolios.py` | `/api/leaderboard`, `/api/portfolios*` | Rankings and portfolio views. |
| `api/orders.py` | `/api/orders`, `/api/trades`, `/api/predictions` | Manual orders and activity history. |
| `api/deps.py` | `get_repo`, `get_engine` | FastAPI dependency accessors. |

---

## 9. API reference

Base URL: `http://localhost:8000` in development, or your deployed backend.
All responses are JSON unless noted.

### System

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Service name, docs path and WebSocket path. |
| GET | `/api/health` | `status: ok`, full simulation status and public settings. |
| GET | `/docs` | Swagger UI (FastAPI). |

### Market

| Method | Path | Query/params | Purpose |
| --- | --- | --- | --- |
| GET | `/api/market/overview` | none | Simulation status, quotes, indices, forecasts, `forecast_meta`, universe and data-source info. |
| POST | `/api/market/forecasts/refresh` | none | Run all three AIs now and record fresh calls without placing orders. |
| GET | `/api/market/quote/{ticker}` | path ticker | Current bar quote for a universe ticker. 404 for unknown ticker or missing bar. |
| GET | `/api/market/history/{ticker}` | `limit` 1–780, default 200 | Visible bars up to the cursor plus SMA5/SMA20 and data info. |
| GET | `/api/market/news/{ticker}` | path ticker; `limit` 1–100, default 30 | Visible headlines for a ticker, or `ALL`/`MARKET`. |

`overview.forecasts` is grouped:

```json
[
  {
    "agent_id": 1,
    "agent_name": "Price AI",
    "model_type": "price",
    "calls": [
      {
        "rank": 1,
        "ticker": "AMD",
        "direction": "UP",
        "expected_pct": 9.37,
        "price": 537.37,
        "expected_usd": 50.35,
        "confidence": 0.88,
        "rationale": "SMA5 ... vs SMA20 ...",
        "sim_time": "2026-02-19T16:00:00",
        "bar_index": 34
      }
    ]
  }
]
```

### Agents

| Method | Path | Query | Purpose |
| --- | --- | --- | --- |
| GET | `/api/agents` | none | All agents with portfolio views and their latest recorded call. |
| GET | `/api/agents/{agent_id}` | path id | One agent, portfolio and latest call. |
| GET | `/api/agents/{agent_id}/portfolio` | path id | Portfolio, positions and full equity curve. |
| GET | `/api/agents/{agent_id}/predictions` | `limit` 1–100, default 25 | Prediction history for one agent. |

`agent_id` is the database agent id, not the portfolio id.

### Portfolios and leaderboard

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/leaderboard` | All accounts, ranked by `total_return_pct` then max drawdown. |
| GET | `/api/portfolios` | Every portfolio view without equity history. |
| GET | `/api/portfolios/manual` | The manual account with positions and equity curve. |
| GET | `/api/portfolios/{portfolio_id}` | Any portfolio with positions and equity curve. |

### Manual orders and activity

| Method | Path | Query/body | Purpose |
| --- | --- | --- | --- |
| POST | `/api/orders` | JSON body below | Queue a manual market order. Returns 201. |
| GET | `/api/orders` | `portfolio_id?`, `limit` 1–200, default 50 | Order history. |
| GET | `/api/trades` | `portfolio_id?`, `limit` 1–200, default 50 | Fill history. |
| GET | `/api/predictions` | `agent_id?`, `limit` 1–200, default 50 | Prediction history. |

Order body:

```json
{
  "ticker": "AAPL",
  "side": "SHORT",
  "quantity": 5,
  "portfolio_id": null
}
```

- `portfolio_id` is optional. Omit it or send `null` to use the manual account.
- Only manual portfolios can be traded through this endpoint.
- `side` must be `BUY`, `SELL`, `SHORT` or `COVER`.
- `quantity` must be an integer from 1 to 1,000,000.
- A successful response includes `order`, `status: "PENDING"`, a `message`,
  `indicative_price`, `estimated_fee` and the current `simulation` status.
- An invalid order returns HTTP 400 with `detail.reason` and
  `detail.message`.

Example:

```bash
curl -X POST http://localhost:8000/api/orders \
  -H 'Content-Type: application/json' \
  -d '{"ticker":"AAPL","side":"BUY","quantity":5}'
```

### Simulation controls

| Method | Path | Body | Purpose |
| --- | --- | --- | --- |
| GET | `/api/simulation/status` | none | Current clock status. |
| POST | `/api/simulation/start` | none | Start/resume; restarts a completed replay. Returns status and snapshot. |
| POST | `/api/simulation/pause` | none | Pause a replay. Returns status. |
| POST | `/api/simulation/reset` | none | Reset accounts/history and the cursor. Returns status and snapshot. |
| POST | `/api/simulation/speed` | `{"speed": 5}` | Set 1, 5, 10 or 30. Returns status; 400 for other values. |
| POST | `/api/simulation/mode` | `{"mode": "live"}` | Switch replay/live; resets accounts. Returns status and snapshot. |

### Simulation status fields

```json
{
  "status": "running",
  "mode": "replay",
  "speed": 5,
  "speed_options": [1, 5, 10, 30],
  "bar_index": 34,
  "total_bars": 251,
  "sim_time": "2026-01-02T16:00:00",
  "session_date": "2026-01-02",
  "start_date": "2025-01-02",
  "end_date": "2025-12-31",
  "progress_pct": 13.9,
  "decision_every_bars": 1,
  "autostart": false
}
```

Live mode adds a `live` object:

```json
{
  "market_open": true,
  "last_poll": "2026-11-12T14:15:00+00:00",
  "session_date": "2026-11-12",
  "poll_seconds": 60,
  "decision_seconds": 300,
  "last_decision": "2026-11-12T14:15:01+00:00",
  "error": null,
  "next_poll_in": 43.2,
  "reference": "Yahoo Finance"
}
```

### Error conventions

- `400` — invalid mode/speed, rejected order, non-manual portfolio order.
- `404` — unknown ticker, agent, portfolio, or missing manual portfolio/bar.
- `422` — FastAPI/Pydantic request validation failure.
- Rejections include a machine-readable `reason` and human-readable `message`
  where applicable.

---

## 10. WebSocket reference

**URL:** `ws://localhost:8000/ws/market` (or `wss://...` behind HTTPS)

On connect, the server immediately sends one full snapshot. Every subsequent
frame is also a full snapshot with `type: "snapshot"`; there are no deltas.

```json
{
  "type": "snapshot",
  "simulation": { "...": "simulation status fields" },
  "quotes": [
    {
      "ticker": "AAPL",
      "price": 275.4,
      "open": 274.1,
      "high": 276.8,
      "low": 273.9,
      "volume": 4200000,
      "previous_close": 273.8,
      "change": 1.6,
      "change_pct": 0.58,
      "ts": "2026-01-02T16:00:00"
    }
  ],
  "indices": [
    { "symbol": "SPX", "name": "S&P 500 (sim)", "level": 6850, "change_pct": 0.4 }
  ],
  "forecasts": [ "... grouped agent forecasts ..." ],
  "leaderboard": [ "... ranked portfolio views ..." ],
  "manual": { "... manual portfolio view ..." },
  "data": { "... data source and live info ..." },
  "server_time": "2026-11-12T14:15:00+00:00"
}
```

- Frames are published on ticks, live polls, play/pause/reset, mode changes and
  data refreshes.
- Each subscriber has a queue of 8 frames. If a client falls behind, the oldest
  frame is dropped rather than stalling the clock.
- If the socket is unavailable, the frontend polls REST every 3 seconds.
- The socket has no authentication and no per-client subscriptions.

---

## 11. Database reference

Default file: `backend/data/simulation.db` (configurable with `DB_PATH`). SQLite
uses WAL mode and foreign keys.

| Table | Columns and purpose |
| --- | --- |
| `agents` | `id`, `name`, `model_type`, `description`, `created_at`. Three seeded strategies. |
| `portfolios` | `id`, `agent_id`, `name`, `kind` (`agent`/`manual`), `starting_balance`, `cash`, `borrow_fees`, `created_at`. Four seeded accounts. |
| `positions` | `id`, `portfolio_id`, `ticker`, `quantity` (signed), `average_entry`, `realized_pnl`, `borrow_fees`; unique per portfolio/ticker. |
| `orders` | `id`, `portfolio_id`, `ticker`, `side`, `quantity`, `status`, `reason`, `source`, `submitted_at`, `sim_time`, `fill_price`, `filled_at`, `fees`. |
| `trades` | `id`, `order_id`, `portfolio_id`, `ticker`, `side`, `quantity`, `price`, `fees`, `realized_pnl`, `sim_time`. Immutable fills. |
| `predictions` | `id`, `agent_id`, `ticker`, `horizon`, `direction`, `confidence`, `expected_pct`, `price`, `rationale`, `sim_time`, `bar_index`. |
| `market_data` | `ticker`, `ts`, `session_date`, `bar_index`, `open`, `high`, `low`, `close`, `volume`; primary key `(ticker, ts)`. |
| `news` | `id`, `ticker`, `headline`, `source`, `sentiment`, `ts`, `bar_index`. |
| `simulation_runs` | Single row (`id=1`): `status`, `mode`, `speed`, dates, `cursor`, `total_bars`, `updated_at`. |
| `data_cache` | Single row: source, interval, fetch time, last bar date, tickers, bar count. |
| `portfolio_snapshots` | `id`, `portfolio_id`, `ts`, `bar_index`, `cash`, `positions_value`, `equity`. Equity curve and drawdown source. |

Order statuses: `PENDING`, `FILLED`, `REJECTED`, `CANCELLED`.

Automatic migrations add `simulation_runs.mode` and
`predictions.expected_pct`, `bar_index`, `price` to existing databases.

`reset_trading()` deletes snapshots, trades, orders, predictions and positions.
`reset_accounts()` also restores every portfolio's cash and clears borrow fees.

---

## 12. Frontend architecture and function reference

### App shell

| Item | Purpose |
| --- | --- |
| `App` | Owns the selected tab, action busy state, action error and header callbacks. |
| `TABS` | Forecasts, Leaderboard, Markets, Trading, Activity; Forecasts is leftmost. |
| `useMarketStream()` | Loads initial snapshot, opens WebSocket, reconnects, falls back to polling, exposes `refresh`. |
| `action(path, body)` | POSTs a header/order action, refreshes the snapshot, handles errors and busy state. |

### Components

| Component | Purpose |
| --- | --- |
| `Header` | Brand, date, status, Replay/Live switch, speed buttons, Start/Pause/Restart, Reset, replay progress. |
| `Overview` | Leaderboard, Markets quote list and Your account panel. |
| `Leaderboard` | Ranked account table. |
| `Markets` | Ticker buttons, selected quote header, chart, stats and data note. |
| `PriceChart` | SVG close-price line/area chart with grid, marker, start/end dates. |
| `Trading` | Manual ticket, account panel, positions and recent orders. |
| `Activity` | Global fills and orders tables. |
| `Forecasts` | Hero call, per-agent top-five lists and forecast note. |
| `Panel` | Reusable titled section. |
| `Empty` | Empty-state paragraph. |
| `Loading` | Loading text. |

### Buttons in the entire UI

| Location | Button count | Action |
| --- | --- | --- |
| Header | 2 | Switch to Replay / Live. |
| Header | 4 | Select 1× / 5× / 10× / 30×. |
| Header | 1 | Start, or Restart when completed. |
| Header | 1 | Pause when replay is running. |
| Header | 1 | Reset. |
| Tabs | 5 | Switch panel. |
| Markets | 8 | Select a ticker. |
| Trading | 4 | Buy, Sell, Short, Cover. |

There are no other clickable controls. Header and trading buttons are disabled
while their action is in flight.

### Client functions

| Function | Purpose |
| --- | --- |
| `apiUrl(path)` | Prefixes a path with `VITE_API_BASE`, stripping a trailing slash. |
| `wsMarketUrl()` | Uses `VITE_WS_URL`, derives `ws(s)://...` from the API base, or uses the page origin. |
| `parse(response)` | Parses JSON and converts HTTP errors into readable `Error` messages. |
| `apiGet(path)` | JSON GET. |
| `apiPost(path, body)` | JSON POST with an empty-object fallback. |
| `useMarketStream().refresh()` | Fetches overview, leaderboard and manual portfolio together. |
| `money(value)` | USD formatting. |
| `signedMoney(value)` | USD with an explicit sign. |
| `signedPct(value)` | Percentage with an explicit plus sign for non-negative values. |
| `signedShares(quantity)` | Signed share count. |
| `toneClass(value)` | Returns `pos`, `neg` or `flat` for colour styling. |
| `simDate(ts)` | Formats a timestamp as a short date. |

### Data flow

1. `useMarketStream` fetches `/api/market/overview`, `/api/leaderboard` and
   `/api/portfolios/manual`.
2. The WebSocket sends full snapshots and replaces the client snapshot.
3. Tab components receive the snapshot as props.
4. Markets and Trading fetch additional history/orders as needed.
5. Header and order actions POST to the API and refresh the snapshot.

---

## 13. Configuration

### Backend environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `CORS_ORIGINS` | `*` | Comma-separated exact allowed browser origins, with scheme and no trailing slash. Use `*` only for a demo. |
| `SIM_AUTOSTART` | `1` | `0`/`false`/`no` boots paused. |
| `SIM_MODE` | `replay` | Initial mode: `replay` or `live`. |
| `MARKET_DATA_SOURCE` | `yahoo` | `yahoo` for real daily bars; `synthetic` for deterministic offline data. |
| `MARKET_DATA_REFRESH_HOURS` | `24` | Minimum age before appending newly completed sessions. |
| `MARKET_HISTORY_RANGE` | `1y` | Yahoo chart range: `6mo`, `1y`, `2y`, etc. |
| `LIVE_POLL_SECONDS` | `60` | Live quote poll interval. |
| `LIVE_DECISION_SECONDS` | `300` | Agent re-evaluation interval in live mode. |
| `DB_PATH` | `backend/data/simulation.db` | SQLite file path. |
| `LOG_LEVEL` | `INFO` | Python log level. |

Some values are read at import/startup time. Restart the backend after changing
them.

### Frontend environment variables

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE` | Backend URL, no trailing slash. Empty means same-origin `/api`. |
| `VITE_WS_URL` | Full WebSocket URL, e.g. `wss://api.example.com/ws/market`. |

These are build-time variables in Vite. They are baked into the generated JS;
changing them requires a rebuild and redeploy.

### Fixed simulation constants

| Setting | Value |
| --- | --- |
| Starting balance | $10,000 per portfolio |
| Universe | AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, META, AMD |
| Transaction fee | 5 bps per side |
| Short borrow | 8% annualized |
| Max long position | 25% of equity |
| Max short position | 20% of equity |
| Max total short exposure | 50% of equity |
| Max order notional | 25% of equity |
| Speeds | 1×, 5×, 10×, 30× |
| Replay bar interval | 1 second at 1× |
| Default replay speed | 5× |

---

## 14. Deployment

### Backend on Render

The repository includes `render.yaml` with a Python web service rooted at
`backend`:

- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/api/health`
- Python version: `3.12.3` via `PYTHON_VERSION` (required because some pinned
  wheels are unavailable on newer Python versions).

Manual settings have the same values. Set `CORS_ORIGINS` to the static site's
exact origin, for example:

```text
https://my-dashboard.onrender.com
```

Multiple origins are comma-separated. No trailing slash, include `https://`.

Render's free filesystem is ephemeral: SQLite data and trade history reset on
restart/redeploy. Attach a Render disk and set `DB_PATH` to a path on it for
durable results.

#### Free-tier sleep and live mode

A free Render web service sleeps after roughly 15 minutes without incoming
traffic. When it sleeps, the background clock and live poll stop, so forecasts
and fills pause until a request wakes the service again. An open dashboard is
not a guaranteed keep-alive, and a closed tab definitely is not.

This repository includes two wake-up paths:

- The frontend calls `/api/health` every four minutes while the dashboard is
  open.
- `.github/workflows/keep-alive.yml` runs every five minutes and pings the same
  health endpoint, keeping the service awake with no browser open. It can also
  be started manually from the Actions tab.

Scheduled GitHub Actions can be delayed and are disabled after long repository
inactivity. For reliable 24/7 live trading, use a paid Render instance or an
external uptime monitor, and confirm the workflow is running. Live decisions
still only occur while the US market is open; after hours the last forecasts are
shown and no new fills occur.

### Frontend on a static host

Build:

```bash
cd frontend
npm ci
VITE_API_BASE=https://your-backend.onrender.com \
VITE_WS_URL=wss://your-backend.onrender.com/ws/market \
npm run build
```

Publish **the contents of `frontend/dist`**, not the source folder:

```text
index.html
assets/index-*.js
assets/index-*.css
favicon.svg
```

Host settings:

- Build command: `npm ci && npm run build`
- Publish directory: `dist`
- SPA rewrite: all paths to `/index.html`

If the site shows a black screen, check the served `index.html`. If it contains
`<script type="module" src="/src/main.tsx">`, the source folder was uploaded
instead of the built `dist`. A static host cannot compile `/src/main.tsx`; upload
the built files so `index.html` references `/assets/index-*.js`.

`VITE_API_BASE` and `VITE_WS_URL` are baked into the bundle. If the backend
origin changes, rebuild the static site.

### CORS and WebSockets

- The backend allows only the exact origins in `CORS_ORIGINS`.
- WebSockets are not subject to browser CORS, but the `wss://` URL must reach
  the backend.
- A preflight failing with 400 usually means the origin is not listed.
- Restart the backend after changing `CORS_ORIGINS`.

---

## 15. Tests

Run:

```bash
cd backend
. .venv/bin/activate
python -m pytest -q
```

Test files cover:

| File | Focus |
| --- | --- |
| `test_trading_engine.py` | Buys, sells, shorts, covers, average entry, fees, borrow, equity identity, rejection paths and next-bar fills. |
| `test_replay.py` | Clock gating, pause/reset, decisions, pending fills, session borrow accrual and completion. |
| `test_market_data.py` | Yahoo parsing, calendar alignment, cache reuse, append refresh, synthetic fallback and retry behavior. |
| `test_live_mode.py` | Live quote parsing, market-open detection, forming bars, live fills and mode switching. |
| `test_api.py` | Health, overview, forecast refresh, leaderboard, manual orders, agent isolation and WebSocket payloads. |
| `test_forecasts.py` | Expected-move direction/bounds, top-five recording, rank order, per-share math, manual refresh and snapshot wiring. |
| `test_yahoo_http.py` | Retryable statuses, backoff, `Retry-After` and attempt limits. |

Current status: **53 passed**.

---

## 16. Troubleshooting

### The page is black

The static host is serving the Vite source `index.html` with
`/src/main.tsx`. Upload the built `dist` contents, not the `frontend/` source
folder. The built `index.html` must reference hashed files under `/assets/`.

### “Cannot reach the backend”

- Confirm the backend URL and that `/api/health` returns 200.
- Check `VITE_API_BASE`; it is build-time, so rebuild after changing it.
- Check the browser console for CORS errors.
- On Render, a free instance may be cold-starting; wait for the health check.

### CORS error / preflight 400

Add the exact static-site origin to `CORS_ORIGINS`:

```text
https://your-site.example
```

Include the scheme, no path, no trailing slash. Restart the backend.

### Forecasts are empty

- The replay is paused at the beginning or has not run enough bars.
- Agents need 20 closes (and enough news history) to produce signals.
- In live mode, no calls are recorded while the market is closed; calls refresh
  on the live decision cadence while it is open.
- Switching mode or Reset clears forecasts.

### Live mode says “market closed”

This is expected on weekends, holidays and outside 09:30–16:00 New York time.
Prices are last known prints. Manual orders queue; no live fills or decisions
occur until the market reopens.

### Orders stay pending

Replay orders fill at the next bar's open, so press **Start**/wait for a tick.
Live orders fill on the next poll while the market is open. After the replay is
complete, reset or restart.

### Data says “Sample data”

Yahoo was unavailable on a cold start or `MARKET_DATA_SOURCE=synthetic` is set.
The simulator is running on deterministic offline prices, not real market data.

### Render build fails on `pydantic-core`

Set `PYTHON_VERSION=3.12.3`. The pinned backend dependencies need wheels that are
not available for newer Python versions on the default build image.

### SQLite data disappears after redeploy

Render's free filesystem is ephemeral. Attach a disk and set `DB_PATH` to a file
on that disk.

---

## 17. Deliberate limitations

- No authentication, user accounts or per-user permissions.
- The manual order endpoint is unauthenticated; treat public deployments as
  demos.
- No real news feed; all headlines and sentiment are simulated.
- No trained ML models, NLP or prediction-accuracy scoring.
- No partial fills, limit orders, stop orders, cancellation UI or margin calls.
- No dividends or corporate-action adjustments beyond Yahoo's raw series.
- No intraday replay chart; replay is daily closes.
- Markets tab has no range picker, zoom or candlesticks.
- Live mode polls once a minute, not streaming tick-by-tick.
- No browser routing/deep links for tabs.
- No dark-mode switch, translations, analytics or social metadata.
- The SPX/IXIC values are synthetic indices derived from the universe; they are
  not real index quotes.
- Activity history is limited to the latest 12 rows in the UI (more through the
  API).
- Equity snapshots are taken per replay bar/live session update, not per trade.

---

## 18. Glossary

| Term | Meaning |
| --- | --- |
| **Bar** | One replay trading session (daily OHLCV) or one forming live session update. |
| **Cursor** | Index of the currently visible bar. All queries are gated by it. |
| **Signal** | An agent's score/confidence/rationale for a ticker. |
| **Intent** | An agent's requested order before validation. |
| **Order** | A queued request; may be pending/filled/rejected/cancelled. |
| **Trade** | An immutable fill created by the exchange. |
| **Fill price** | Price used when an order executes: next replay open or next live quote. |
| **Long** | Positive position; profits when price rises. |
| **Short** | Negative position; profits when price falls. |
| **Cover** | Buy back shares to reduce a short. |
| **Equity** | Cash plus mark-to-market position value. |
| **Drawdown** | Decline from a previous equity peak. |
| **Expected move** | Model estimate of the next five sessions' percentage move. |
| **Forecast batch** | The top five calls an agent records for one decision/bar. |
| **Replay** | Historical daily-bar simulation. |
| **Live** | Real-quote simulation during the US session. |
| **Forming bar** | Today's still-changing live OHLCV bar. |
| **Basis point (bp)** | 1/100th of a percent; 5 bps = 0.05%. |
