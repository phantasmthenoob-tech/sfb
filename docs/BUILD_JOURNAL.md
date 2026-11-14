# Build Journal — AI Market Simulator

> **A fictionalized, composite build journal.** The dates, incidents, log lines,
> conversations and people below are invented for documentation and portfolio
> purposes. The application itself is real; this narrative is not a literal
> historical record. It is written as a realistic engineering diary so the
> design and debugging decisions are easy to explain to someone new to the
> project.

This journal starts on **11/09/26** with design work only. No backend code and no
frontend code existed until the Figma system was signed off on **11/10/26**.
The first backend commit is on **11/11/26**; the first frontend commit is on
**11/18/26**. The journal then follows the project through launch, the first
users, the ugly deployment failures, the quieter hardening work, and a long
post-launch period of experiments, dead ends and architecture decisions, ending
on **01/08/27**.

There are **56 entries** across **61 dates**. Some days are not listed. I have
a lot of homework now and I take breaks, so **11/15/26, 11/21/26, 11/22/26,
11/28/26 and 11/29/26** are full rest days rather than missing work. Every other
date in the range has an entry, including the weekends and holidays when I
worked lightly. The 11/14 entry is a logged light day, not a skipped one.

These entries are written at the end of each day, which is why they have the
shape they do: a plan in the morning, coding and debugging in the middle, a
problem in the afternoon, and a slightly more honest version of the plan at
night. Some days do not have a dramatic problem. I left those days quiet
instead of inventing one.

I started on **11/09/26**, but I did not make a document version of that first
entry at the time. I am copying the early notes onto this document now, so the
first few days are reconstructed rather than pasted from a daily file.

## Timeline at a glance

| Date | Main focus | Defining moment |
| --- | --- | --- |
| 11/09/26 | Figma discovery and wireframes | The first dashboard tried to show everything |
| 11/10/26 | Figma system, prototype and sign-off | Design was “done” but the handoff was not |
| 11/11/26 | Architecture and backend skeleton | The first API contract did not match the design |
| 11/12/26 | Trading engine and accounting | Look-ahead bias and incorrect short equity |
| 11/13/26 | Replay clock, order lifecycle, risk limits | Fills, locks and the first impossible leaderboard |
| 11/14/26 | Design reflection and pacing | Learning to stop touching the code |
| 11/16/26 | Yahoo daily data and caching | Rate limits, partial sessions and slow starts |
| 11/17/26 | Live mode, websockets, background tasks | Duplicate engines and a clock that would not sit still |
| 11/18/26 | First frontend code and API integration | The design looked nothing like the first render |
| 11/19/26 | Dashboard tabs, chart and trading UI | Tables, labels and mobile clipping |
| 11/20/26 | Forecasts and top-five rankings | A forecast that read like a promise |
| 11/23/26 | First Render deployment | Python 3.14, CORS and environment variables |
| 11/24/26 | Static hosting and launch | The black screen, stale bundle and 404 routes |
| 11/25/26 | First users and mobile feedback | Confusing empty states and small type |
| 11/26/26 | Performance, SQLite and persistence | Slow queries, WAL files and resets |
| 11/27/26 | Forecast accuracy and security review | Confidence versus certainty; public controls |
| 11/30/26 | Deployment rehearsal and hardening | A clean room found three missing settings |
| 12/01/26 | Quiet failure and monitoring | A socket that failed while the page looked fine |
| 12/02/26 | Handoff, docs and Figma cleanup | Deciding what not to build |
| 12/03/26 | Final verification and freeze | The last bug was a wording bug |
| 12/04/26 | Retrospective and closing | What I would do differently |
| 12/05/26–12/12/26 | Post-launch review, mobile Safari, caching and ML experiments | Two detours that looked promising and wasted days |
| 12/13/26–12/19/26 | Postgres and delta-WebSocket experiments | Both ideas were correct in theory and wrong for this app |
| 12/20/26–12/26/26 | Mobile polish, live holidays, Yahoo outage, disk rehearsal | Operational reality after launch |
| 12/27/26–01/01/27 | SSR, auth and rate-limit prototypes | Scope explosions before the final freeze |
| 01/02–01/05/27 | Architecture records, regression pass, final docs | The last decisions were about what not to build |
| 01/06/27 | Render sleep and live mode | The engine was fine; the service was asleep |
| 01/07/27 | Forecast lookbacks and Predict now | A quiet day; deciding what the model should admit it sees |
| 01/08/27 | The black screen returned | The app was fine; the host was serving source |

---

## Day 1 — 11/09/26

### Morning: starting with a blank Figma file instead of a blank editor

I opened Figma before I opened a terminal. That was deliberate. The previous
project I built started with a database schema and ended with a UI that looked
like a database schema. This time I wanted the opposite: decide what a person
sees, in what order, and why, before writing a single route.

The brief was simple on paper: three AI portfolios, one manual portfolio, a
replay of real market data, a leaderboard, and a way to buy and sell. The first
frame was not simple at all. I tried to fit the leaderboard, a watchlist, the
manual account, a chart, recent orders and a news feed onto one 1440 px canvas.
It looked impressive in a screenshot. It felt like a cockpit designed by someone
who had never flown a plane.

I sent the frame to Nina, a designer friend who has a gift for saying the thing
I am avoiding. She replied: “This is three products stacked on top of each
other. Which one is the user here for?” I knew the answer. The user is here to
see whether the AIs are beating them. Everything else is supporting evidence.

That answer became the first real design decision: **Leaderboard first**,
markets and the manual account second, everything else on separate tabs. The
leftmost tab in the final build would be Forecasts, but the default screen would
be the competition. That ordering survived every later argument.

### Afternoon: the Figma problems started immediately

The first Figma problem was auto-layout. I built the leaderboard as nested
frames with “hug contents” on every cell. In Figma, that made the columns breathe
with the content and look alive. In a real table, it meant the numeric columns
changed width depending on whether the value was `$10,000.00`, `0.00%`, or `—`.
When I prototyped a few states, the account names jumped left and right. It was
the design equivalent of a table with no column widths. I rebuilt the row around
fixed numeric columns and a flexible name column, and the whole dashboard
immediately felt calmer.

The second problem was density. At 1440 px the three-column layout worked. At
1280 px the chart labels collided with the right rail. At 1100 px the right rail
became a stack of cards that pushed the leaderboard below the fold. I was
designing for my monitor, not for a browser window. I added a 1120 px content
cap, a single-column collapse below 900 px, and a rule that no panel could
contain more than two primary numbers.

The third problem was contrast. The white theme used a very light gray for
secondary text. It looked elegant on my calibrated display and nearly vanished
on a laptop in a bright room. I darkened the muted and faint tokens and checked
the numbers at normal zoom. The design became a little less “editorial” and a
lot more readable. I also stopped using light gray for anything a user needed to
make a decision.

### Evening: naming the thing before building the thing

The last decision of the day was the name of the forecast tab. I had written
**Predictions**. It sounded smart. It also implied the AI knew what was going to
happen. Nina asked whether a user would understand that a negative number was a
short idea rather than a loss. I did not have a good answer.

We changed the label in Figma to **Forecasts** and the copy to “expected move.”
I wrote a note in the Figma file: “A forecast is an estimate with uncertainty.
Do not let the UI turn it into a tip.” That note came back to save me several
times.

I closed Figma at 7:15 p.m. with wireframes, a rough type scale, and no code. I
felt impatient. I also felt something I had not felt on the previous project:
the sense that the hard product questions had been asked before the first
commit, not after.

### End of day

No repository. No backend. No frontend. Just a design direction and a list of
things the dashboard was not allowed to become. It was the right place to
start, even if it did not feel like progress.

---

## Day 2 — 11/10/26

### Morning: turning screens into a system

The second day was about making the design repeatable. A single pretty frame is
not a design system; it is a screenshot. I built the components that the app
would actually reuse: panel, table, numeric cell, ticker row, order button,
status tag, empty state, loading state, and the header control group.

The Figma component variants caused their own small problems. A button had
default, hover, active, disabled and “busy” states, but the busy label was a
different width, so the row jumped when a request was in flight. I fixed the
width and used an ellipsis. The table had a “positive” and “negative” text
variant, but the variant names were not used consistently, so a P&L cell could
inherit the wrong colour when I copied a row. I renamed the variants and stopped
using colour overrides for anything that represented a value. The design file
became less flexible and more reliable, which was the correct trade.

The chart was the hardest component. I wanted a clean line with a subtle area
fill, four price grid lines and dates at both ends. In Figma, I could fake it
with a vector and some text. In the browser, it would have to scale from a wide
desktop card down to a phone without the labels turning into dust. I specified a
760-unit viewBox, a 74-unit right gutter for price labels, and a rule that the
chart could shrink but never hide its last price. That specification later
became the actual SVG implementation almost line for line.

### Afternoon: the prototype review

At 2 p.m. I walked Nina through a clickable prototype. The flow was: Leaderboard
→ Markets → select ticker → Trading → submit order → Activity. She clicked
through it twice and then asked the question that changed the forecast design:
“Where do I see what the AIs think before they trade?”

I had buried the forecast tab at the end of the tab bar because it felt like a
secondary feature. She argued it was the most interesting part of the product:
the AIs are making claims, and the user should see those claims before the
trades, not after. We moved **Forecasts** to the far left. It would not be the
default tab, but it would be the first thing the eye found when the user wanted
to know why the leaderboard was moving.

The prototype also exposed a mobile problem before any code existed. The tab bar
wrapped after four items at 390 px. The fifth tab fell onto a second line with
no divider, so it looked like a different control. We changed the tab bar to a
horizontally scrollable row with a subtle fade at the edge. The design file now
had a real mobile frame, not a squeezed desktop frame.

### Evening: design sign-off, and the rule that followed

At 6:42 p.m. Nina and I signed off on the Figma file. The components were named,
the states were documented, the desktop and mobile frames existed, and the copy
had survived a hostile read. I wrote a short handoff note:

- 1120 px content cap.
- Leaderboard is the default tab.
- Forecasts is the leftmost tab.
- White background, dark text, no colour-only meaning.
- All tables have fixed numeric columns.
- Empty states explain what the user should do next.
- A forecast is an estimate, never a guarantee.

Then I made a rule for myself: **no backend or frontend code until the design is
signed off**. I had broken that rule on previous projects and paid for it with
weeks of UI rework. This time the repository would stay empty until the next
morning.

I felt relieved and slightly terrified. The design was done. Now I had to build
something worthy of it.

### End of day

Figma was complete before a single line of application code existed. That
sounds like a small process detail. It was actually the decision that kept the
next two weeks from turning into a sequence of rewrites.

---

## Day 3 — 11/11/26

### Morning: the first commit

I created the repository at 9:10 a.m. The first commit was not a feature. It was
a README, a `.gitignore`, and a directory skeleton. I sat there for a minute
before typing the commit message because it felt like the point of no return.
Then I wrote `chore: initialize project` and moved on.

The architecture came from the design, not the other way around. The dashboard
needed a clock, quotes, portfolios, forecasts, orders and a websocket. That
mapped cleanly to a small FastAPI app with SQLite, a simulation engine, a
trading engine, AI strategies and a read-only API layer. I drew the boundaries
on paper:

- Agents produce signals and order intents. They do not touch money.
- The order manager queues intents.
- The exchange validates and fills them.
- The clock decides what data is visible.
- The API exposes read models; it does not own the simulation.

That separation was the most important code decision of the project. It also
made the first week slower, because every feature had to pass through a boundary
instead of being a quick mutation in a route handler.

### Afternoon: the first API contract did not match the design

I wrote the first market overview endpoint and a mock response before the
frontend existed. The design had a leaderboard table, a quote list and an account
summary. I returned them as separate top-level keys. Then I wrote a small
OpenAPI note and realized the collection shapes were inconsistent: one endpoint
returned a bare array, another returned `{ "entries": [...] }`, and a third
returned `{ "quotes": [...] }`.

I standardized on named envelopes for every collection. It felt fussy at the
time. It saved the frontend from a class of `data.map is not a function` errors
later, when the frontend and backend were finally connected.

The first real integration failure happened against `curl`, not React. I sent a
string quantity to the order endpoint and got a 422 with a nested validation
detail array. My error handler assumed `detail` was a string, so it printed
`[object Object]`. I fixed the handler before the UI existed. That was a small
mercy I gave my future self.

### Evening: SQLite and the first lock

SQLite was the obvious choice for a single-user demo: no external service, no
credentials, easy to inspect, easy to delete. I enabled WAL mode and foreign
keys. The first version opened a new connection per request, which worked until
the replay loop and an HTTP request wrote at the same time. I saw
`database is locked` for the first time and felt a familiar sinking feeling.

The fix was a single connection guarded by a re-entrant lock, shared by the
engine and the API. WAL mode stayed. It was not a scalable design, but it was a
correct design for one process. I wrote that limitation down before it could
become an accidental architectural claim.

I went to bed with a backend that could return quotes and a database that did not
yet contain a single trade. It was not much, but it was a foundation.

### End of day

The first backend commit existed. The design was still intact. The repo had a
shape, and the shape had rules.

---

## Day 4 — 11/12/26

### Morning: the first trade felt like magic, which was the warning

The first buy worked. I submitted five shares, saw a pending order, advanced the
clock, and watched the position appear in the portfolio. I actually said “yes”
out loud. Then I looked at the leaderboard and felt the floor drop.

The AI accounts were making absurd returns. Not “good” returns. Impossible
returns. The kind of returns that make you check whether you accidentally
divided by one hundred instead of multiplying. The first replay was filling
orders at the same close price the agent had used to make the decision. The
agent could see the answer and then buy at the answer.

That was look-ahead bias, and it was hiding in plain sight. The fix was to
separate decision time from execution time: orders stay pending until the next
bar's open. The replay loop fills pending orders first, then advances the clock,
then asks for new decisions. The leaderboard became less exciting and much more
believable.

I wrote the sequence on a sticky note and stuck it to the monitor:

1. Fill yesterday's orders at today's open.
2. Advance the clock.
3. Mark positions at today's close.
4. Ask the agents what they think now.
5. Queue their orders for tomorrow.
6. Snapshot equity.

That note stayed there for the rest of the build.

### Afternoon: the short that doubled the account

The next bug was worse because it looked plausible. Opening a short position
made equity jump by roughly twice the notional. The sale proceeds went into
cash, and the position value was also being treated as a positive asset in one
of the summary paths. For a few minutes I thought I had discovered free money.
Then I remembered that free money in a backtest is almost always an accounting
bug.

The fix was signed positions everywhere: long quantities are positive, short
quantities are negative, and market value is `quantity × price`. A short
contributes a negative value. The cash proceeds are real, but the liability is
real too.

I wrote the equity identity on the same sticky note:

```text
equity = starting_balance + realized_pnl + unrealized_pnl
         - fees_paid - borrow_fees
```

Then I wrote tests that bought, sold, shorted and covered, and asserted that
identity after every step. The tests caught three more problems: fees were only
charged on buys, borrow fees were charged once instead of daily, and average
entry used a simple average instead of a quantity-weighted blend. Each fix made
the AI accounts look worse and the engine look better.

### Evening: the first green test run

At 10:40 p.m. the accounting tests went green. I sat in the kitchen with a cold
cup of coffee and felt an emotion I can only describe as suspicious relief. The
numbers balanced. The short did not create money. The fees were real. The
leaderboard was still mostly empty, but it was honest.

I closed the laptop without starting the next feature. That was unusual for me.
The accounting work had taken longer than planned, and I was learning that
“longer than planned” is often the price of not lying to yourself.

### End of day

The engine could trade without cheating. It could short without inventing
equity. It could charge fees without pretending they were optional. It was
finally safe to build the clock around it.

---

## Day 5 — 11/13/26

### Morning: orders are not trades

The next design decision was to keep orders and trades separate. An order is an
intent; a trade is a fill. That sounds obvious until you build a UI that wants to
show “recent activity” and you realize you need both: the order that is still
pending, and the fill that actually changed the money.

I added an order status lifecycle: `PENDING`, `FILLED`, `REJECTED`,
`CANCELLED`. Every order stores its source (`manual` or `ai:price`, etc.),
submission time, simulation time and fill details. Every fill creates an
immutable trade row. A pending order can be rejected at fill time if cash or
limits have changed. That last detail mattered: validation at submission is not
enough, because the world moves between submission and fill.

I also added the replay clock. It is a cursor over daily bars, not a wall clock.
Every read is cut at the cursor. Every fill uses the next bar's open. The
simulation status persists so a restart can resume where it stopped. The clock
became the spine of the whole app.

### Afternoon: risk limits and the first rejected order

The first risk-limit implementation was too permissive. It checked cash at
submission but not at fill, and it did not cap order notional separately from
position size. I could submit an order that passed at submission and then failed
at fill because the price had moved. That was realistic, but the UI had no way to
explain it. I added the rejection reason and surfaced it in the order table.

The rules became deliberately strict:

- BUY cannot be used while short the same ticker.
- SELL cannot open a short.
- SHORT cannot be used while long the same ticker.
- COVER cannot open a long.
- A long cannot exceed 25% of equity.
- A short cannot exceed 20% of equity.
- Total short exposure cannot exceed 50% of equity.
- An order that increases exposure cannot exceed 25% of equity.
- Exits are never blocked by the order-size cap.

The strictness felt annoying while testing. It also made the demo explainable. A
user can understand why a button refused an order if the reason is “you cannot
sell shares you do not own,” not “internal error.”

### Evening: the websocket was born as a delta stream

The first websocket implementation sent deltas. One frame for a new quote, one
for an equity change, one for an order. The frontend would merge them into local
state. In theory it was efficient. In practice it was a reliability trap.

I missed one frame during a restart and the dashboard stayed permanently out of
sync. React StrictMode opened the socket twice in development and produced
duplicate connections. A delta stream plus duplicate connections is a recipe for
state that looks fine in one tab and wrong in another.

I replaced the deltas with full snapshots. Every frame contains the complete
dashboard state. It is larger, but a dropped frame is harmless because the next
frame is newer. StrictMode can open and close an extra socket without corrupting
anything. The decision was not elegant, but it was robust. I have never regretted
choosing robust over elegant for a demo websocket.

### End of day

The backend could replay, trade, reject and broadcast. The frontend still did
not exist. The design was frozen, the engine was behaving, and I was exhausted
in the good way that comes from fixing real problems.

---

## Day 6 — 11/14/26

### Morning: not opening the code editor

I woke up thinking about the live mode I had not built yet. I made coffee, sat
down at the desk, and then deliberately did not open the code editor. The design was
signed off. The backend had a spine. The next step was another large feature, and
I knew from experience that starting it on a Saturday morning after a late Friday
would produce a lot of code and very little judgment.

I went for a walk instead. I thought about the difference between a replay and a
live simulation. In replay, the clock is an index. In live, the clock is the
actual clock. The same engine cannot pretend those are the same thing without
lying about fills, market hours and stale quotes.

That walk produced the decision to keep live mode explicitly separate: a
different polling path, a different market-hours check, a forming bar for today,
and a clear “market closed” state. It was the most useful work I did all day, and
it did not involve a terminal.

### Afternoon: design notes from the future

I opened Figma for twenty minutes, not to change the design, but to write notes
against the existing frames. The forecast panel needed a state for “no calls
yet.” The live header needed a “market closed” status. The trading ticket needed
a disabled state for a completed replay. The design had most of these states,
but not all of them.

I added annotations, not new screens. The Figma file stayed signed off. This was
a subtle but important distinction: the design was complete enough to build
against, and implementation discoveries could be documented without reopening
the whole visual direction.

I also wrote a short list of things I was not allowed to add during the build:
a dark mode, a second chart type, a news feed panel, a forecast accuracy score,
and a login screen. The list was a promise to my future self. I broke it twice,
but never for anything that shipped.

### Evening: the fear before live mode

I went to bed early. I was nervous about live mode in a way I had not been about
replay. Replay is deterministic. Live mode depends on Yahoo, the market clock,
the network, and the difference between “the price now” and “the price the order
deserves.” There were more ways for it to be wrong.

I wrote one line in my notebook: “Do not let live mode fill at a price it has
already shown the user as a decision input.” That became the design constraint
for the next day.

### End of day

No commits. No new features. A better mental model. Some days that is the whole
job.

---

## Day 7 — 11/16/26

### Morning: Yahoo Finance did not want to be our data vendor

The first daily-data download worked on my laptop and failed on the second run.
Yahoo's public chart endpoint returned HTTP 429 after several rapid requests for
eight tickers. The initial code treated any non-200 response as fatal, so the
whole startup failed even though seven symbols had downloaded successfully.

I added a shared HTTP helper with bounded retries for 429, 500, 502, 503 and 504.
Three attempts per host, exponential backoff starting at 0.5 seconds, jitter,
an 8-second cap, and a second host if the first failed. I also made one bad ticker
non-fatal for live quotes. A single unavailable symbol should degrade the
dashboard, not kill the poll.

The first retry implementation made the startup slower in a way that felt like a
hang. Three attempts per host times two hosts is six requests per ticker when
Yahoo is down, and eight tickers run concurrently. I added a shorter timeout and
made the fallback to cached data explicit. “Slow” is not a failure mode users can
distinguish from “broken,” so I treated it as one.

### Afternoon: the partial day was a look-ahead bug in disguise

The daily endpoint includes the current session while the market is open. My
first replay imported that partial day. The “close” was an intraday price, and
the replay could see a session that had not finished. Another look-ahead path,
this time from the data provider instead of the fill logic.

I added a New York-time cutoff: while the market is open, only completed sessions
are eligible. The cutoff is based on the market close, not UTC midnight. This
sounds like a small detail until a developer in another timezone runs the app at
5 p.m. Eastern and gets a different dataset than a developer in London at 10 p.m.
local.

Calendar alignment was the next data bug. Different tickers occasionally
returned different numbers of sessions around holidays. Concatenating them by
index produced a timeline where one ticker's day 40 was a different date from
another's. I built a shared calendar from the union of dates, forward-filled a
missing ticker with its previous close and zero volume, and rejected datasets
with fewer than 60 sessions or a ticker missing more than half the calendar.

### Evening: the cache made the second start feel instant

The first cold start downloaded a year of daily bars, generated simulated
headlines, wrote thousands of rows and seeded accounts. It took long enough that
I thought the app had crashed. The second start was fast because the data was
already in SQLite.

I made the cache explicit: a `data_cache` row records the source, fetch time,
last bar date, tickers and bar count. If the cache is younger than the refresh
window, reuse it. If it is stale, append only newly completed sessions. If Yahoo
is unreachable and there is no cache, fall back to deterministic synthetic data
and label it clearly.

The first cold start is still slower than I would like. The difference is that
it is now a known cost, not a mystery. I wrote the expected startup sequence in
the README so the next person would not spend an hour debugging a download that
was simply doing its job.

### End of day

Daily data was cached, retries were bounded, and the replay could no longer see
an unfinished session. I felt a new respect for data providers. They are not a
utility; they are a dependency with moods.

---

## Day 8 — 11/17/26

### Morning: live mode has a second clock

Live mode was the largest source of scope creep. Replay is a loop over bars.
Live mode needs the real clock, a market-hours check, a forming daily bar, quote
polling, fills on new prints, and agent decisions on a slower cadence. I kept
catching myself trying to reuse the replay tick for live updates. They look
similar from the outside and behave differently in every important detail.

I made the separation explicit. A live poll fetches quotes, checks whether the
market is open and the quotes are fresh, updates or creates today's forming bar,
marks positions, fills pending orders at the latest print, and only then decides
whether the agents should re-evaluate. If the market is closed, none of the
session mutations run. The last prices stay visible and the header says
**Live · market closed**.

The first version filled an order in the same poll that received it. That made
manual orders look instant even though the UI promised “next quote.” I separated
queueing from filling. A manual or agent order is queued; the next live poll
fills pending orders. It matched the replay promise and removed a whole class of
same-tick decisions.

### Afternoon: two workers, two engines, one very confused leaderboard

`uvicorn --workers 2` looked like a harmless way to improve throughput. It was
not. Each worker created its own `SimulationEngine`, both polled Yahoo, both
wrote to the same SQLite database, and both published to their own in-memory
websocket subscribers. The leaderboard flickered between two states. Orders
appeared twice. The clock advanced at double speed in one tab and normal speed
in another.

I spent an hour thinking I had a race condition in the database before I
remembered that the event manager is in-process. There is no shared bus between
workers. The app is a single-instance design by construction.

I removed the second worker and wrote the limitation down: one process, one
engine. Scaling horizontally would require a shared clock, a shared database
write coordinator and a shared pub/sub layer. Calling the current design “highly
available” would be a lie.

### Evening: websocket failures and the reconnect loop

The first websocket client retried immediately on close. When the backend was
restarting, the browser produced a tight loop of connection attempts and filled
the console with “WebSocket is closed before the connection is established.” It
looked like a catastrophic failure. It was a retry policy that had no patience.

I changed the retry to 2.5 seconds, added REST polling every three seconds while
the socket was down, and made every frame a full snapshot. Malformed frames are
ignored rather than closing the stream. The connection still fails during a
deploy, but it recovers quietly.

I also learned that a WebSocket failure is not always a WebSocket problem. If
the URL is wrong, the handshake never reaches the app. If the proxy does not
forward the Upgrade header, the request may return 200 and still never upgrade.
If the page is HTTPS and the URL is `ws://`, the browser blocks it as mixed
content. The console message is often less specific than the cause.

### End of day

Live mode had its own clock, one process, and a reconnect policy that did not
panic. I went to bed with the backend feature-complete enough to start the
frontend. That was a sentence I had been waiting two weeks to write.

---

## Day 9 — 11/18/26

### Morning: the design finally became software

The first frontend commit was on 11/18, eight days after the Figma sign-off.
That gap was intentional. The backend contract existed, the data shapes were
known, and the design had not been quietly rewritten while I was coding. I
created the Vite app, added the TypeScript types, and built the shell before
touching a single API call.

The first render was disappointing. The Figma frame had generous whitespace and
crisp columns. The browser had a default font, a table with no width rules, and a
panel that stretched to the full width of a 27-inch monitor. It looked like a
wireframe that had been left in the sun.

The problem was not the design. The problem was that Figma had been drawn at a
fixed width and the browser was fluid. I added the 1120 px cap, the shared panel
component and the type scale from the handoff. The second render looked like the
design. I took a screenshot and sent it to Nina with the message: “It’s alive,
and it’s only slightly ugly.”

### Afternoon: the API shape mismatch

The first API integration failed exactly where the design and the backend
disagreed. The frontend expected `{ entries: [...] }`; the endpoint returned a
bare array. The page fetched successfully, then `entries.map` threw a
`TypeError`, and React unmounted the entire dashboard. In development the Vite
overlay explained it. In production it would have been a blank panel with no
clue.

I standardized every collection response and updated the shared types before
wiring the next component. I also made the API client understand structured
errors. FastAPI returns a 422 with a list of validation details; my first error
handler assumed `detail` was a string and displayed nothing useful. After the
fix, a bad quantity produced “Enter a positive number of shares” instead of
“Request failed (422).”

The first CORS failure happened the same afternoon. The frontend was on port
3000 and the API on port 8000. In development the Vite proxy hid the problem. I
tested the separate-origin path, the browser sent a preflight, and the backend
returned 400 because `CORS_ORIGINS` was still a placeholder. Seeing a working
proxy and a broken direct request at the same time was the most useful CORS
lesson of the project.

### Evening: the websocket met React StrictMode

React StrictMode opened the websocket twice in development. One connection
closed before it finished establishing, producing the warning that would follow
me for the rest of the build. The app still worked because every frame is a full
snapshot, but the console looked like a disaster.

I spent an hour trying to eliminate the warning before accepting that it was a
development-only double-mount, not a production bug. I added cleanup, a disposed
flag and a retry timer, and left the warning alone. The important behavior was
that the page recovered from a closed socket and fell back to polling. It did.

### End of day

The dashboard could load, show a leaderboard, switch tabs and receive a
snapshot. It was the first day the project felt like a product instead of a set
of APIs.

---

## Day 10 — 11/19/26

### Morning: tables are where designs go to die

The leaderboard table was the first component that looked better in Figma than
in the browser. The design had fixed numeric columns and a flexible account
column. The implementation had a table with auto layout, so the account name
pushed the return column around. At desktop width it was tolerable. At 1100 px
the max-drawdown column clipped.

I added explicit column classes: rank, account, and right-aligned numeric
columns. I also stopped formatting numbers inside the table cell component and
moved formatting to the boundary, so a value could be sorted and coloured
without changing its textual width. The table became less “designed” and more
readable, which was the point.

The Markets tab had a similar problem with the chart. The SVG used a 760-unit
viewBox and scaled to the container. At 390 px the price labels were tiny and
the date labels overlapped. I increased the right gutter, reduced the number of
grid labels on narrow screens, and made the chart height responsive. The chart
still had no zoom, tooltips or candlesticks. That was a deliberate limitation,
not an oversight.

### Afternoon: the trading ticket

The trading ticket was the first place where the UI had to explain a rule it
could not enforce alone. The buttons could be disabled, but the final validation
happened on the server. I added a client-side check for a positive share count,
but I did not duplicate the cash, position and short-exposure rules. If the
client and server disagreed, the server won.

The first version of the ticket let the user submit an order for a ticker that
was not in the current quote list. The server rejected it with an unknown-ticker
error, and the UI displayed the error in a red banner above the tab. That was
technically correct and experientially poor. I made the ticker a select populated
from the snapshot, so the invalid state could not be reached through the normal
UI.

The positions table was another Figma casualty. The design showed a “Close”
button on each row. The actual API only supports Sell and Cover, and the
direction depends on whether the position is long or short. I removed the fake
button and kept the ticket as the single place to act. Fewer buttons, fewer
ways to be wrong.

### Evening: the first screenshot that felt like the product

At 8:20 p.m. I loaded the app with a running replay, a populated leaderboard, a
green market list and the trading ticket. It looked like the Figma frame. Not
identical, but recognizably the same product. I felt a rush of pride that
surprised me. I had spent so long looking at tables and logs that I had forgotten
the thing was supposed to be seen.

Then I opened it on my phone and remembered. The tabs wrapped. The table
scrolled sideways. The forecast rows did not exist yet, but I could already
predict they would be the worst of the lot. I added mobile to the next day’s
list and closed the laptop.

### End of day

The dashboard had tabs, a chart, a ticket and a leaderboard. It also had a list
of responsive problems that would take another week to finish. That is the
normal shape of frontend work: the screenshot is the beginning, not the end.

---

## Day 11 — 11/20/26

### Morning: one headline call was not enough

The first forecast implementation recorded one call per agent: the single
largest expected move. The Forecasts tab showed three cards, one per AI, each
with a ticker and a percentage. It looked clean. It also looked like three stock
tips.

The request was to show the top five expected moves per AI, ordered by size,
with the percentage and the per-share value. That turned a simple card into a
ranked list and forced a database change. The `predictions` table had been
designed for one row per agent per bar. I added `expected_pct`, `bar_index` and
`price` with in-place migrations, then changed the recording path to compute all
non-flat estimates, sort by absolute move, take the first five and replace the
agent's calls for the bar in one transaction.

Replacing instead of appending mattered. In live mode an agent can make several
decisions during one forming bar. Appending would mix stale and fresh ranks.
Deleting the agent/bar batch first kept the list coherent.

### Afternoon: the flat list became grouped, and the frontend crashed

The API shape changed from a flat list to grouped agent blocks with a `calls`
array. The frontend had been written against the flat shape, so the first reload
threw `Cannot read properties of undefined (reading 'map')` inside the Forecasts
tab. The page did not go fully black because the tab was not the default, but
clicking Forecasts produced an empty panel and a console error.

I updated the shared types, the websocket mapping and the component in the same
change. This was a reminder that renaming a field is a breaking change even when
the field name stays the same; the nesting changed, and every consumer had to
know.

The backend also had a direction bug. The stored `direction` came from an entry
threshold, while the displayed percentage came from the continuous estimate. A
signal just below the threshold could show `-4.98%` but store `FLAT`, so the arrow
and the number disagreed. I made direction follow the sign of the estimate. The
old threshold helper stayed for callers that want a three-state classification,
but forecasts no longer use it.

### Evening: a forecast is not a promise

Nina read the new tab and said, “This looks like you’re telling me what to buy.”
She was right. The hero said “Biggest expected win,” the rows were ranked, and
the confidence number looked like a probability. A user could easily read `-6.13%`
as a loss instead of a short opportunity.

We changed the language: **Forecasts**, **rise/drop**, **estimated move per
share**, and a note explaining that a drop is a candidate short and that the
figures are model heuristics. The confidence value stayed, but the surrounding
copy made clear that it was signal confidence, not the chance of making money.
The backend caps it at 95% and never claims certainty.

I felt uneasy shipping a feature that looked more authoritative than it was. The
copy helped. The honest answer was that the model was a baseline, not a crystal
ball, and the UI needed to say so.

### End of day

Each AI had a top-five list, the numbers agreed with the arrows, and the tab no
longer read like a tip sheet. It was the last feature before deployment. I was
proud of it and a little afraid of it, which is probably the correct emotional
mix for anything that makes a prediction.

---

## Day 12 — 11/23/26

### Morning: Render chose Python 3.14

The backend deployment failed before it served a request. Render's default
Python runtime had moved to 3.14. The pinned `pydantic-core==2.27.2` had no wheel
for that version, so pip tried to build from source. The build installed
`maturin`, attempted to compile Rust, and failed because `/usr/local/cargo` was
read-only. The visible error was a wall of Cargo output. The actual problem was
one version number.

I stared at the log for ten minutes before I saw it. The failure felt personal.
The app ran locally. The tests passed. The only difference was the platform's
default interpreter. I set `PYTHON_VERSION=3.12.3`, redeployed, and the wheel
installed in seconds.

That was the first time I felt the gap between “works on my machine” and “works
on a server” as a physical thing. It is not one bug. It is a stack of assumptions
about the interpreter, the filesystem, the network and the browser that all
happen to be true on your laptop.

### Afternoon: CORS, again, with feeling

The static frontend had the correct API URL, but the backend had the placeholder
`CORS_ORIGINS`. The browser blocked the first request. The dashboard showed a
connection error. I added the real origin, restarted the backend, and verified
the preflight with curl.

The frustrating part was that I had already fixed CORS locally. The local Vite
proxy made the frontend and backend look same-origin, so the browser never sent
the request that would have failed. The deployed site was the first honest test.

The fix was exactness: scheme, host, no path, no trailing slash. A trailing slash
in `CORS_ORIGINS` produces a value the browser will never send. I wrote that in
the deployment notes in capital letters, then went back and fixed the parser to
strip trailing slashes so the next person would not have to read the capital
letters.

### Evening: the backend took forever to wake up

The first page load after a deploy sat on “Connecting…” long enough that I
assumed it was broken. Render's free instance was waking from sleep, and the
engine was loading cached data. The health check eventually returned 200, but the
dashboard had no way to say “the service is awake, the first snapshot is still
coming.”

I separated the concepts in the documentation: health check, data load, engine
start, first snapshot. The UI still collapses them into one loading state, which
is acceptable for a demo but not for an operator. I added a cold-start note to
the README and resisted the urge to add a spinner with a fake progress bar. A
fake progress bar would have made the wait feel longer, not shorter.

### End of day

The backend was live. The frontend was not yet loading data. I had a working API
and a static site that could not talk to it. It was 11:30 p.m. and I went to bed
with the CORS error looping in my head.

---

## Day 13 — 11/24/26

### Morning: the black screen

The static site returned 200 and showed a completely black page. The host's
status page was green. The build had succeeded. My first assumption was a
JavaScript crash, so I opened the console and found nothing useful. Then I viewed
the served HTML.

It contained:

```html
<script type="module" src="/src/main.tsx"></script>
```

The source folder had been uploaded instead of `frontend/dist`. A static host
cannot compile `/src/main.tsx`. The browser requested it, received the wrong
content type or a 404, and React never mounted. The black screen was not a React
bug, a CSS bug or a CORS bug. It was an upload bug.

I felt a hot wave of embarrassment. I had written the deployment instructions
myself. I had tested the local build. I had still dragged the wrong folder into
the upload box.

The fix was to upload the **contents** of `dist`: `index.html`, the hashed
`assets/` folder and `favicon.svg`. The page rendered immediately. I added a
release check: view source, confirm the script tag points to `/assets/index-*.js`,
and only then call the deploy done.

### Afternoon: the 404 after the black screen

With the built site loading, a refresh on a tab path returned 404. The dashboard
uses tabs, not routes, so the path was artificial, but a host health check or a
shared link could still request it. The static host needed an SPA rewrite sending
all paths to `/index.html`. Once that was in place, `/`, `/markets` and a random
path all served the app.

I also found that the deployed frontend was still calling the old API host. The
bundle had been built before `VITE_API_BASE` changed. Vite variables are
compile-time constants; redeploying the same files does not update them. I
rebuilt, checked the old hostname was absent from the bundle, and uploaded again.

The WebSocket failed for a third reason: the URL was `ws://` on an HTTPS page,
which the browser blocks as mixed content. Changing it to `wss://` fixed the
handshake. By the end of the afternoon I had fixed the API URL, the CORS origin,
the static upload, the SPA rewrite and the WebSocket scheme. Each one had looked
like “the site is broken.”

### Evening: launch, quietly

At 8:10 p.m. the dashboard loaded on the public URL with real data. The
leaderboard was moving. The forecast tab showed three AIs and their top five
calls. I sent the link to two friends and then closed the laptop before I could
start refreshing the logs.

I did not feel triumphant. I felt like someone who had just fixed five unrelated
things and was waiting for the sixth. That was probably the healthiest possible
launch emotion.

### End of day

The app was live. The black screen was gone. The static routes worked. The
WebSocket connected. The next morning would bring the first users who had not
read the README.

---

## Day 14 — 11/25/26

### Morning: the first user found the confusing part immediately

A friend opened the link on his phone and asked why his account was at $10,000
while Price AI was at $9,987.40. He had read the top row of the leaderboard as his
account because it was at the top. The `manual` tag was small and light gray. On
a phone, the agent names were visually heavier than the word “You.”

I felt a familiar sting. The design had been reviewed on a desktop. The first
external user was on a phone, in a hurry, reading the biggest number nearest his
thumb. We made the manual tag stronger and moved the account summary higher on
the mobile layout. It was a tiny change. It was also the most important usability
fix of the week.

The forecast rows had the same problem in a different form. At 390 px, the
ticker, direction, percentage, price and per-share value all competed for one
line. The percentage pushed the per-share estimate off the card. We changed the
row to two lines: identity and direction on top, price and estimated move below.
It looked less dense and read much better.

### Afternoon: the stale bundle and the timezone

A small copy change did not appear after a deploy. The HTML was cached and
pointed at the previous hashed bundle. The new assets were on the server, but the
browser never requested them. I hard-refreshed and saw the new text, which meant
the deploy was fine and the cache policy was not.

I added a release step: verify the script filename in the served HTML, and serve
`index.html` with a short cache lifetime while keeping hashed assets immutable.
Hashed filenames only make caching safe if the HTML is revalidated.

The same day someone asked why the header date and the chart date disagreed near
midnight Eastern. The simulation time is stored as an ISO timestamp, and the
frontend formats the date portion directly. For daily bars stamped at 16:00 that
is fine; around a UTC boundary it is not. I standardized date-only display on the
session date and stopped passing raw UTC instants into a date formatter. The
conversation about “which date is the truth” was longer than the fix.

### Evening: the live empty state

Switching to Live after the market closed showed no forecasts. The engine was
correct: no new decisions were being made from stale prices. The UI was not. It
said “No calls yet. Start the replay,” which was exactly the wrong instruction
for someone already in Live mode.

I drafted copy explaining that the market was closed and that calls would appear
after the next open. I did not change the engine to fabricate forecasts from
Friday's closes. A forecast recorded against stale data is worse than no
forecast because it looks current. We added the copy to the release notes and
made the limitation explicit in the README.

### End of day

The first users found the manual-account confusion, the mobile clipping and the
live empty state. None of those were architectural. All of them were real. I
went to bed thinking that launch is not the moment the product is finished; it
is the moment other people start finishing it for you.

---

## Day 15 — 11/26/26

### Morning: the leaderboard was doing too much work

The first performance profile was embarrassing. `/api/leaderboard` took about
700 ms warm and felt much worse on a cold Render instance. The page loads the
leaderboard three times in quick succession: the initial REST refresh, the
WebSocket snapshot, and the manual portfolio request.

Each portfolio view was loading its positions, trade statistics and up to 500
equity snapshots. With four portfolios that was a dozen queries per leaderboard
build, and the leaderboard was rebuilt inside every snapshot. SQLite was fast,
but we were asking it to repeat work for data that had not changed.

I confirmed the hot indexes, stopped fetching the full snapshot history for the
leaderboard view, and left the equity curve on the portfolio detail endpoint
where it belongs. Warm requests dropped to a couple of hundred milliseconds. It
was not a dramatic benchmark win, but the dashboard stopped feeling sticky.

### Afternoon: the snapshot was larger than it needed to be

The WebSocket sends a full snapshot on every tick. That is deliberate, but it
does not mean every field must be recomputed from scratch. The frame includes
simulation state, eight quotes, two synthetic indices, three forecast blocks,
four leaderboard entries, the manual portfolio and data-source metadata.

I trimmed fields the dashboard never reads and kept the full objects on the REST
endpoints where they are useful. The frame got smaller without changing visible
behavior. The bigger lesson was that “full snapshot” should mean “full enough to
render,” not “serialize the entire database.”

The database growth conversation came next. Every replay tick writes one equity
snapshot per portfolio. At 251 bars and four portfolios that is about a thousand
rows, which is trivial. Live mode can write a snapshot every poll, and a
long-running demo can accumulate rows quietly. I added a retention note and a WAL
checkpoint to the operational checklist.

### Evening: copying the database while it was running

I copied `simulation.db` while the app was running and got a database that looked
empty. The recent writes were still in the WAL file. The data was not lost; the
copy was incomplete. The correct procedure is to stop the service or checkpoint
the WAL, then copy the database and its WAL/SHM companions.

This was not a code bug. It was the kind of operational trap that turns into a
false “SQLite lost my data” story. I documented it next to the persistence note:
Render's free filesystem is ephemeral; attach a disk and set `DB_PATH` if history
matters; back up all three files or none.

### End of day

The app was faster, the socket was lighter, and the backup procedure was
written down. None of it was visible in a screenshot. All of it made the demo
less likely to embarrass us under load.

---

## Day 16 — 11/27/26

### Morning: “which one is going to win?”

A user asked the question every forecast feature invites: “Which one is actually
going to happen?” I explained that none of them is a promise, that the numbers
are model estimates, and that the ranking is by absolute expected move, not
probability of success. He asked whether the highest-confidence AI had the best
track record. I had to say we did not have a scored track record yet.

That was uncomfortable. The app showed three AIs, a leaderboard and a forecast
tab, so it looked like it knew which AI was best. The leaderboard measures
simulated portfolio returns, which depend on sizing, fees, timing and luck as
much as signal quality. Confidence is a monotonic transform of the raw score,
capped at 95%. A 90% confidence call is not right nine times out of ten.

We considered adding a forecast accuracy column and decided against it. A proper
evaluation needs a fixed horizon, a definition of correctness, a benchmark and
enough closed forecasts to avoid noise. A green/red badge would have looked
scientific and been meaningless. We added the limitation to the README instead.

### Afternoon: percentages versus dollars

The next question was why a 3% move ranked above a 6% move. The answer was price:
the 3% move was on a higher-priced stock, so the dollar move per share was
larger. The user was thinking in dollars; the model ranks in percentages. We show
both, but the ordering is percentage-based.

We debated changing the rank to absolute `expected_usd`. A $500 stock moving 2%
is a $10 move; a $100 stock moving 6% is a $6 move. If “biggest win” means
per-share dollars, the first should rank higher. If it means percentage move, the
second should. The app does not know the user's position size, so neither ranking
is universally right. We kept percentage because it is comparable across stocks
and because the forecast is fundamentally a percentage estimate. The per-share
value is context, not the sort key.

### Evening: the security review we had been avoiding

The app was about to be shared more widely, so we did a threat-model pass. The
first finding was obvious: there is no authentication. Anyone who can reach the
API can submit manual orders, reset accounts, switch modes and start or pause the
simulation. CORS is not an authorization boundary; it is a browser policy. A
script or direct HTTP client can call the endpoints regardless of allowed
origins.

For a single-user demo this is a deliberate tradeoff, but it needed to be stated
plainly. We added a warning to the README: treat a public deployment as a demo,
not a competition with real stakes. We checked that SQL uses bound parameters,
that ticker and side values are validated, that non-manual portfolios cannot be
traded through the manual endpoint, and that no secrets are committed. None of
this makes the app production-grade. It makes the obvious abuse paths understood.

I felt uncomfortable publishing a reset button that anyone could press. The
honest fix was a warning and a future auth plan, not a half-finished login screen
bolted onto the last week of the build.

### End of day

The feature did not get more accurate. It got more honest. For a paper-trading
demo, that was the right kind of improvement.

---

## Day 17 — 11/30/26

### Morning: a clean-room deployment

The app had been deployed several times, which is different from being
deployable. We created a fresh Render service and a fresh static site and tried
to reproduce the setup from the README alone, without looking at the old
dashboard settings.

The rehearsal failed in three places. The backend used the platform's default
Python instead of 3.12.3, and the `pydantic-core` source build appeared again,
followed by the Rust/Cargo error. The new static site was built without
`VITE_WS_URL`, so REST worked but the socket tried to connect to the static host;
the polling fallback kept the page looking alive, which made the failure quiet.
And the backend's `CORS_ORIGINS` still contained the old hostname, so the new
site's preflight returned 400.

Each fix was one line. Finding them took the morning because each failure looked
like a different kind of broken. That is the nature of integration work: the
symptoms are visible, the causes are configuration.

### Afternoon: the black screen returns

The clean-room static site showed a black screen again. This time we knew where
to look. The served HTML contained `/src/main.tsx`. The upload had included the
entire `frontend/` folder instead of the contents of `frontend/dist`. The browser
could not compile the source entry point.

We replaced the upload with the dist contents and confirmed the HTML referenced
hashed assets. Then we tested a deep link and got a 404 because the SPA rewrite
was missing. The two failures are easy to conflate because both produce a blank
or missing page. They are not the same:

- **Wrong upload:** `/` loads HTML but the JS entry point is uncompiled source.
- **Missing rewrite:** `/` works, but any path other than `/` returns 404.

We added both checks to the release checklist, along with “view source and
confirm the hashed bundle name.” The checklist is boring. It is also the reason
the next deploy worked.

### Evening: persistence, again

The fresh backend had no persistent disk, so a redeploy reset the accounts. The
behavior was expected, but watching it happen in a clean environment made the
user-facing consequence obvious: anyone who had been trading lost their history
without warning. For a demo, that is acceptable only if it is stated. We added
the Render disk instructions and the `DB_PATH` note to the README.

We also tested the backup path with the WAL files present. Copying only the main
`.db` file produced an older state. The correct procedure is to stop the service
or checkpoint the WAL before copying. This is the kind of detail that does not
belong in the UI but absolutely belongs in the runbook.

### End of day

The clean-room rehearsal found three config gaps and two static-hosting traps
before a real user did. It was tedious and repetitive and exactly the kind of
work that prevents launch-week firefighting.

---

## Day 18 — 12/01/26

### Morning: the dashboard that looked fine while the socket was dead

A deploy changed the WebSocket host, but the REST base URL stayed the same. The
dashboard loaded, the leaderboard updated every three seconds through the polling
fallback, and nothing looked wrong. The socket was dead the entire time.

I only noticed because I opened the network panel to check something else. The
fallback is a feature, but it can hide a broken real-time path. The page looked
alive while the live stream was not connected. For a user, that is fine. For an
operator, it is a blind spot.

We added a connection indicator to the backlog and wrote down the rule: if the
socket is down for more than a few seconds, surface it. The UI already has
enough status text, so we did not rush a new badge into the release. The bigger
lesson was that resilience can mask failure. A fallback should degrade the
experience, not erase the evidence.

### Afternoon: the empty forecast that looked like a bug

A user switched to Live on a Saturday and saw an empty Forecasts tab. The engine
was correct: the market was closed and no decisions were being made. The UI was
not. The empty state told them to start the replay, which was the wrong
instruction for someone already in Live mode.

We drafted copy explaining the market hours and added it to the release notes.
We did not fabricate forecasts from stale prices. A forecast recorded against
Friday's close and displayed as “live” on Saturday is worse than an honest empty
state. The limitation went into the README next to the live-mode rules.

### Evening: the small panic

For about ten minutes I thought the backend had lost all the data. The
leaderboard was empty, the manual account was missing, and the health endpoint
returned a fresh simulation. Then I remembered the clean-room service was still
pointed at a new, empty database. Nothing was lost. I was looking at the wrong
deployment.

I wrote that down too. Most “data loss” incidents in small projects are
environment confusion. Check the hostname, the database path and the service
before assuming the worst. The second check is cheaper than the panic.

### End of day

No code changed. The monitoring gap and the empty-state wording were documented.
Sometimes the most useful engineering work is admitting what the system hides.

---

## Day 19 — 12/02/26

### Morning: feature freeze

Friday was a feature freeze. No new panels, no new metrics, no “while we're in
here” refactors. The only acceptable changes were documentation, test fixes and
bugs that blocked the core loop.

We ran the full backend suite, the TypeScript build and the production bundle
build. We loaded each tab in the browser and checked the empty states. We opened
the site at a narrow width. We verified the deployed HTML referenced the hashed
bundle, the API preflight succeeded and the WebSocket connected with `wss://`. We
exported a fresh dist archive and labeled it as the deployable artifact.

The final numbers were modest: eight tickers, four portfolios, three AI
strategies, up to five forecasts per AI per decision, 52 backend tests and a
single-page dashboard. The project did not need to be bigger. It needed to be
understood.

### Afternoon: documentation as a product feature

We wrote the README as if a new maintainer had to run the project without asking
questions. That meant documenting the failure modes, not just the happy path:
what a black screen means, why a preflight can fail, why the database resets,
why live forecasts disappear after hours, and why a forecast is not a promise.

We also cleaned up the Figma file. The original frames had accumulated variants
that never shipped, and the narrow layout was still represented by a single
squeezed desktop frame. We added a real mobile frame, documented the responsive
breakpoints, and marked the forecast component's two-line row as the canonical
layout. The design file and the code finally told the same story.

The journal became part of the handoff. Writing it forced us to admit which
problems were design problems, which were implementation problems and which were
deployment problems. The black screen was not a React bug. The CORS failure was
not a backend bug. The database reset was not a data-loss bug. They were all
integration failures, and they all looked like “the app is broken” from the
outside.

### Evening: the last bug was a wording bug

At 6:30 p.m. Nina read the Forecasts tab one more time and stopped at the word
“confidence.” She said, “I still think this means you know what will happen.”
She was right. The number was capped at 95%, but the label did all the wrong
work.

We did not have time to redesign the component. We changed the surrounding copy
to “signal confidence” and added the sentence that a forecast is a model
heuristic, not a guarantee. It was a wording fix, not a model fix, and it was the
most important change of the day.

### End of day

The release was frozen. The docs were written. The design file was tidy. I felt
the particular tiredness that comes from finishing something you care about and
knowing it is still imperfect.

---

## Day 20 — 12/03/26

### Morning: the final walkthrough

I walked through the app as a new user one last time. Leaderboard, manual tag,
Markets, select a ticker, Trading, place a small buy, watch it stay pending,
Start, watch it fill, Forecasts, read the note, Activity. Nothing surprising
happened. That was the best outcome available.

I checked the page on a phone, on a narrow laptop window and on a wide monitor.
The tables held their columns. The forecast rows stacked. The chart labels were
small but readable. The header controls wrapped without overlapping. None of it
was beautiful in every size, but all of it was usable.

I read the README top to bottom and found two stale details: a default that had
changed and a screenshot path that no longer existed. I fixed them and closed the
file. Documentation rots quickly; the only defense is reading it as a stranger.

### Afternoon: the emotional part

I have built projects that looked better than this one and worked less well. I
have built projects that shipped faster and taught me less. This one was
different because the hard parts were invisible: the fill that had to wait for
the next bar, the short that had to carry a negative value, the forecast that had
to admit it was an estimate, the deploy that had to survive a different Python
version.

I felt proud of the engine and embarrassed by the number of times I uploaded the
wrong folder. I felt relieved that the accounting tests passed and sad that the
project was ending. I felt a little ridiculous for being emotionally attached to
a paper-trading demo. But that is what happens when you spend two weeks with a
thing and try to make it honest.

Nina sent a message: “It looks like the Figma now.” I replied: “It behaves like
the Figma now, which is harder.” That was the whole project in one exchange.

### Evening: what I would do differently

I would define the API envelopes and TypeScript types before the first component.
I would write the accounting tests before the first trade. I would put the
deployment checklist in the repository on day one. I would use the word “signal”
instead of “confidence” and “forecast” instead of “prediction” from the very
first Figma frame.

I would also protect the design phase more aggressively. Finishing Figma before
touching the backend was the best decision of the project. There were moments
when it felt like wasting time, especially on 11/10 when the design was “done”
and I was impatient to code. But every later UI decision had a reference, and the
frontend never had to invent a layout while also inventing an API.

### End of day

The build was complete. Not perfect. Complete.

---

## Day 21 — 12/04/26

### Morning: the launch deploy

The launch deploy was uneventful. The Python version was pinned. The CORS origin
was exact. The static upload contained the dist contents. The SPA rewrite was in
place. The HTML referenced the current hashed bundle. The WebSocket connected
with `wss://`. The health check returned 200. The dashboard loaded.

I watched the replay for a few minutes. Price AI bought something. News AI
disagreed. Combined AI took a smaller position. The leaderboard moved by a few
dollars. The forecast panel showed five calls per AI with percentages, prices and
per-share estimates. It was ordinary, which meant it was working.

### Afternoon: closing the launch phase

I wrote the launch-phase summary in the late afternoon with the laptop plugged
in and a cup of coffee going cold beside it. The project still has limits I would not
hide: simulated headlines, single-instance background tasks, polling instead of
streaming, no authentication, and an ephemeral database on free hosting. The
engine is a baseline, not a market-beating model. The forecasts are estimates,
not promises.

But the core loop is coherent. Decisions are made from visible data. Orders fill
later. Positions are signed correctly. Fees and borrow costs are charged.
Forecasts are labeled as estimates. The dashboard explains what it is showing,
and the documentation explains what it is not.

I would do the next version differently. I would start with the same Figma
discipline, then add authentication and a real forecast-accuracy study before
adding another feature. I would keep the single-process architecture until the
product actually needed more. I would write the deployment checklist before the
first deploy, not after the fifth failure.

### Evening: the thing I want to remember

The thing I want to remember is not the black screen or the Python error. It is
the moment on 11/10 when the design was signed off and the repository was still
empty. I had made the space to think before building. Everything that worked
later started there.

The app is a paper-trading simulator. It is also a record of a hundred small
decisions about what to show, what to hide, what to call a forecast and what to
admit when the numbers are uncertain. That is the part I am proudest of.

I closed the laptop at 5:40 p.m. and did not open it again that day.

### End of the launch phase

---

## Day 22 — 12/05/26

### Morning: the silence after launch

The dashboard had been live for a little over a week. The first users had come
and gone. The logs were mostly health checks and a few page loads. I woke up on
Saturday with the strange emptiness that follows a launch: the thing I had been
chasing for a month was now just a URL that occasionally got a visitor.

I read the backend logs with fresh eyes. There was no error monitoring, no
request tracing, no alert when the process died. I had been the monitoring
system. If something broke at 2 a.m., I would find out when I opened the page.
That was acceptable for a demo and unacceptable for anything else. I wrote
“observability” on the backlog and did not pretend a dashboard was the same
thing as production readiness.

### Afternoon: the post-launch list

I made three lists: things that were actually broken, things that confused
people, and things I wanted to build because they were interesting. The third
list was the longest. I put a line between the second and third lists and wrote:
“Do not confuse curiosity with priority.”

The actually-broken list had two items: a mobile layout issue in Safari and an
intermittent stale-bundle problem after deploys. The confusing list had the live
empty state, the meaning of confidence, and the fact that a down forecast looked
like a loss. The interesting list had forecast accuracy scoring, a second chart
type, authentication and a real news feed. None of the interesting items made
the product more correct that week.

### Evening: deciding to experiment carefully

The next two weeks were going to be experiments. I had a stable baseline and a
small amount of user feedback, which is the best time to try architecture changes
because you can measure them against something real. I made a rule: every
experiment gets a branch, a success criterion and a time box. If it misses the
criterion, it gets deleted, not defended.

I did not follow that rule perfectly. The journal is honest about the ones I
kept alive too long. But writing the rule down made the failures easier to
recognize.

### End of day

No code. A plan and a slightly uncomfortable awareness that “it works” is not
the same as “it is finished.”

---

## Day 23 — 12/06/26

### Morning: Safari made the page feel broken

A friend sent a screenshot from an iPhone. The trading tab looked fine until
the keyboard opened, at which point the order button was pushed below the
visible viewport and the page jumped when the keyboard closed. On desktop this
was invisible. In Safari on iOS it felt like the app was fighting the user.

The first instinct was to add a `visualViewport` hook and recalculate the layout
on every resize. I spent an hour on it. The hook worked, but it introduced a
render loop during fast typing and made the page feel jittery. The simpler fix
was CSS: allow the page to scroll, stop using `100vh` for the shell, respect the
safe-area inset, and keep the order buttons in the normal document flow. It was
less clever and it worked.

### Afternoon: the mobile audit

I went through every tab at 390 px and wrote down what actually broke:

- The tab bar wrapped instead of scrolling cleanly.
- The leaderboard table clipped the max-drawdown column.
- The ticker list was comfortable, but the chart labels were tiny.
- The forecast rows tried to fit five values on one line.
- The order ticket’s submit buttons were visible, but the notice appeared below
the fold after submission.

None of these were new. They had been visible on 11/25, but I had fixed the
symptoms I noticed and moved on. This time I fixed the layout rules: tables get
horizontal scroll only as a last resort, numeric columns stay right-aligned,
forecast rows become two lines, and feedback messages appear above the buttons.

### Evening: the value of a boring fix

I closed the `visualViewport` branch without merging it. The CSS fix was six
lines. I had spent an hour on the hook and ten minutes on the solution. That
ratio would repeat several times in the next month. The lesson was not “never
try the clever thing”; it was “try the boring thing first, then earn the right to
be clever.”

### End of day

The page worked on Safari. The keyboard no longer ate the buttons. I felt a small,
disproportionate satisfaction.

---

## Day 24 — 12/07/26

### Morning: the sparkline temptation

The forecast rows were accurate but visually flat. I wanted to add a tiny
sparkline beside each ticker: a miniature price line that made the call feel
alive. I built a quick SVG component in an hour. It looked great in isolation.

In the actual row it was a disaster. The sparkline competed with the percentage
for attention, made the card taller, and turned every row into a tiny chart that
was too small to read and too busy to ignore. Nina looked at it for three seconds
and said, “Now I have to decode five charts before I can read five numbers.”

I removed it before lunch. The branch was deleted. The only thing I kept was the
sparkline math, which I did not use.

### Afternoon: hierarchy instead of decoration

The real problem was that the row did not have a clear hierarchy. The ticker,
direction, percentage, price and per-share value all carried equal visual weight.
I changed the row to make the ticker and percentage primary, the direction a
small label, and the price/per-share line secondary. No new component. No new
data. Just weight, spacing and order.

That was the first time I understood why designers keep talking about hierarchy.
It is not a aesthetic preference. It is a way to keep a user from reading five
things when they only need two.

### Evening: a note from a user

A user wrote: “I like the app, but I don’t know which number is the important
one.” That message could have been a brief. I added it to the backlog and
resisted the urge to reply with a long explanation of the model. The interface
should answer that question without a paragraph.

### End of day

The sparkline was gone. The row was quieter and easier to scan. One less thing
to maintain.

---

## Day 25 — 12/08/26

### Morning: the caching idea that made everything worse

I decided to add TanStack Query (then React Query) for API caching. It is a good
library. It has sensible defaults, request deduplication, retries and a clean
cache model. I was convinced it would simplify the data layer and reduce the
number of requests after tab switches.

I installed it on a branch and wrapped the overview, leaderboard and manual
portfolio fetches. Within an hour I had a second source of truth. The WebSocket
was already pushing full snapshots, and React Query was caching REST responses
with different timestamps. A tab switch could show an older REST value after a
newer socket frame had arrived. The UI flickered between the two.

### Afternoon: fighting the cache

I tried invalidating the queries on every socket frame. That worked, but it
meant every frame triggered three refetches, which was worse than the original
code. I tried disabling refetch-on-focus and setting stale times to infinity.
Then the cache never updated. I tried a custom query key that included the
simulation bar index. That made the cache grow by one entry per tick.

By 4 p.m. I had a complicated data layer that was slower and more confusing than
the twenty-line hook it replaced. The socket snapshot was already the cache. I
was adding a cache for the cache.

### Evening: deleting two days of work

I deleted the branch. Two days of work, gone. I felt stupid, then relieved. The
original design was not accidental; every frame is a full snapshot because that
is the simplest correct model for this app. REST is a bootstrap and a fallback,
not a parallel state store.

I wrote an architecture note: **the websocket snapshot is the source of truth;
REST is for the initial load and explicit refreshes.** The frontend keeps one
snapshot object, and tab components derive from it. No query cache, no
normalized store, no duplicate invalidation graph.

### End of day

I lost two days and gained a rule I would not have trusted without losing them.

---

## Day 26 — 12/09/26

### Morning: pagination for twelve rows

The Activity tab shows the latest twelve orders and trades. I decided it needed
cursor pagination so it could show more. I sketched an API with `before_id`,
`limit`, `has_more` and a “Load more” button. I wrote half the backend query and
a frontend hook before I stopped and asked what problem I was solving.

There was no user request for more history. The API already supports a limit of
200, and the dashboard deliberately shows a short recent list. Adding pagination
would have added a button, a loading state, an error state, a cursor that could
go stale after a reset, and a bug surface around duplicate rows. For twelve rows.

### Afternoon: deleting the branch

I closed the branch. It lasted four hours. I wrote a note: “Do not add a
mechanism for a problem the UI does not have.” The API already exposes history;
the dashboard does not need to become a log viewer.

Instead I spent the afternoon making the empty and error states clearer. If the
orders request failed, the table silently stayed empty. That was a real problem,
because an empty table and a failed request look identical. I added an error
message that distinguishes “no orders yet” from “could not load orders.” No new
endpoints. No pagination. Just honesty.

### Evening: a small architecture win

The deliberate non-decision felt better than a feature. Every mechanism you add
has to be maintained, tested and explained. The best code is sometimes the code
you do not write.

### End of day

No feature shipped. The UI became clearer. That counted.

---

## Day 27 — 12/10/26

### Morning: how would we know if a forecast was right?

I started designing a forecast accuracy metric. The obvious version is: after
five sessions, compare the realized return to the predicted percentage. If the
direction matches, count it as a win. That sounds simple until you ask what
“direction matches” means for a 0.4% forecast, or whether a 5% move in the wrong
direction should count the same as a 0.1% miss.

I wrote three candidate definitions:

1. Direction-only hit rate: sign of realized return equals sign of forecast.
2. Threshold hit rate: realized return beats a minimum magnitude in the called
   direction.
3. Error score: mean absolute error between forecast and realized return.

Each one told a different story. Direction-only made the model look good in
choppy markets. Threshold made it look bad because most five-day moves are small.
MAE punished a correct but conservative call. None of them captured whether the
forecast was useful for a position-sized decision.

### Afternoon: the missing sample

I also did not have a clean evaluation dataset. Forecasts are recorded per bar,
but switching modes resets predictions. Live predictions are sparse. The top-five
list is replaced on every decision, so a naive query would score only the latest
batch and call it history. I would need to preserve every forecast batch, define
a fixed horizon, join it to future bars and handle mode resets. That was a real
feature, not an afternoon script.

I wrote the design down and did not build it. The UI would not show an accuracy
number until the evaluation was defensible. A green badge with no sample size
would have been worse than no badge.

### Evening: the discipline of not shipping a number

I am a sucker for a dashboard metric. A percentage feels like progress. But a
forecast accuracy score is one of those numbers that can be technically correct
and deeply misleading. I put the design in the backlog under “research,” not
“quick win.”

### End of day

No accuracy score. A better definition of what it would take to earn one.

---

## Day 28 — 12/11/26

### Morning: the ML detour

I had a dangerous idea: replace the heuristic forecast with a small logistic
regression or gradient-boosted model. The app already had features, labels and a
clean simulation loop. How hard could it be?

I installed scikit-learn on a branch. I built a training set from technical
features: SMA spread, momentum, volatility, sentiment, volume change. I labeled
the next five sessions as up or down. The first model reported 71% accuracy. I
felt a rush of excitement. Then I remembered that I had used the same bars for
training and testing.

### Afternoon: leakage everywhere

I split the data by time and the accuracy dropped to the low 50s. I tried a
walk-forward split. Still low. I added more features and got a slightly better
in-sample fit and a worse out-of-sample result. I standardized the features using
statistics from the full dataset, which leaked future information. I fixed that
and the number dropped again.

The final model was not better than the heuristic in any way that mattered. It
was less interpretable, added a dependency, required serialization, and would
have made the forecast rationale impossible to explain. The heuristic is not
smart, but it is transparent: score times volatility. A user can read it.

### Evening: deleting the model

I removed scikit-learn and the branch. I had spent two full days on a model that
was worse than the baseline. I was angry at myself, then grateful that I had not
shipped it. The lesson was not “ML is bad.” The lesson was “do not add a model
without a benchmark, a split and a reason.”

I wrote a note for the README: forecasts are a transparent heuristic, not a
trained model. That sentence was true before the experiment and easier to defend
after it.

### End of day

Two days gone. A stronger appreciation for the baseline. A slightly bruised ego.

---

## Day 29 — 12/12/26

### Morning: cleaning up the evidence

I removed the ML dependency, the training script and the notebook. I kept a
short markdown note with the results: in-sample accuracy, walk-forward accuracy,
why the split mattered, and why the model was rejected. Deleting the code without
recording the result would have made it too easy to try the same thing again in
three months.

I also checked the lockfile and the Python requirements to make sure the
experiment had not left a transitive dependency behind. It had. I removed it and
rebuilt the environment from scratch to prove the app still ran without it.

### Afternoon: the emotional hangover

I did not want to look at forecasts. I spent the afternoon on small, concrete
things: copy edits, a broken link in the README, a test that was asserting the
wrong reason string. The work was boring in the best way. After two days of
chasing a model, I needed tasks with unambiguous completion criteria.

I also went back to the user email about “which number is the important one” and
rewrote the forecast note. The answer was not a better model. The answer was a
clearer explanation of the existing one.

### Evening: a walk and a decision

I walked to the park and decided not to pursue a trained model for this version.
The product needed calibrated expectations more than it needed a marginal
accuracy improvement. If I ever added a model, it would need a proper evaluation
harness, a baseline comparison and a way to explain the output. That was a
project, not a feature.

### End of day

The branch was gone. The lesson stayed.

---

## Day 30 — 12/13/26

### Morning: the Postgres idea

The single-process limitation kept bothering me. If the app were ever going to
run on more than one instance, SQLite and the in-memory event manager would have
to go. I decided to prototype a Postgres-backed version. It was a reasonable
architecture experiment: move the repository to a real database, run two
workers, and see whether the app could scale horizontally.

I installed Postgres locally, created a schema, and started porting the
repository. The first few queries were easy. Positions, orders and trades mapped
cleanly. The schema was already relational. I began to feel optimistic.

The optimism lasted until I reached the simulation clock. The clock is not just
a row in a table; it is an in-process cursor, a background task, a live polling
loop and an event publisher. Two workers with two clocks would each advance
their own cursor. The database could serialize writes, but it could not make two
loops agree on when a bar had advanced. The second worker would either duplicate
decisions or skip them.

### Afternoon: the architecture exposed itself

I kept going because I wanted the experiment to succeed. I added a Postgres
advisory lock around the clock tick. That made one worker wait for the other, but
it did not solve the event fan-out: a websocket connected to worker A would not
receive a snapshot published by worker B. The browser would see one clock half
the time and another clock the other half.

The correct design would have been a separate scheduler process, a shared job
queue, a shared pub/sub layer and a websocket gateway. That is a real
architecture, and it is much larger than this demo. I had been treating “use
Postgres” as if it were the same thing as “make the app distributed.” It is not.

### Evening: stopping before the sunk cost won

I had a working half-migration and a strong urge to finish it because I had
already spent the day. That is the sunk-cost trap. The migration would have added
operational complexity, a network dependency and a new class of failure modes
without improving the single-user experience. I stopped.

I wrote the first architecture decision record: **one process, one clock, one
SQLite connection.** If the product ever needs multiple instances, the clock,
the event bus and the websocket layer move out first; the database is the easy
part. That was a much better sentence than “we should use Postgres.”

### End of day

A half-finished branch and a clearer architecture. I felt foolish and relieved
in roughly equal measure.

---

## Day 31 — 12/14/26

### Morning: trying to prove myself wrong

I went back to the Postgres branch in the morning because I did not want to
abandon an idea just because it was hard. I ran two backend instances against the
same database and watched the leaderboard. For a few seconds it looked fine. Then
the orders doubled.

Both workers had loaded the same pending orders. Both filled them. The database
serialized the writes, so the result was not corruption; it was duplication. The
same economic decision was executed twice. The cash still balanced because each
fill was internally consistent, but the portfolio had traded twice as much as it
should have.

The websocket made the problem visible: one browser tab was connected to worker
A and received A's snapshots; another tab was connected to worker B and received
B's. The two leaderboards disagreed by a few dollars. It looked like a rendering
bug. It was two universes.

### Afternoon: the part that would have taken another week

I listed everything a real multi-instance version would need:

- A single scheduler with a distributed lock or leader election.
- A shared event bus for websocket fan-out.
- Idempotent order filling keyed by order id and clock version.
- A migration path for the in-process event manager.
- Health checks that distinguish “connected to the database” from “owns the
  clock.”
- A deployment model that does not accidentally run two schedulers.

That was not a database migration. That was a distributed-systems project. I
closed the branch.

### Evening: deleting the branch and telling the truth

I deleted the Postgres branch and removed the local container. I felt the
specific frustration of wasted time: two days, a schema, a repository port and a
lot of hope, all gone. But the alternative was worse: shipping a fragile
half-distributed system and calling it scalable.

I wrote in the README: “The app is deliberately single-instance. Multiple
workers would duplicate the clock and the event stream.” That sentence was worth
the two days. It prevented a future maintainer from making the same mistake.

### End of day

The app was still on SQLite. The architecture was smaller, but the reasoning was
stronger.

---

## Day 32 — 12/15/26

### Morning: cleaning up the migration

I spent the morning deleting the Postgres branch, the Docker compose file and
the unused dependency. I exported the SQLite database before touching anything,
because even a failed experiment should not put the demo data at risk. The export
included the WAL checkpoint, which I had learned to do the hard way.

I wrote a short ADR with three sections: context, decision, consequences. The
decision was not “SQLite is better than Postgres.” It was “this app’s correctness
depends on a single clock and a single event stream, so the simplest deployment
is one process.” The consequences were explicit: no horizontal scaling, no
multi-user isolation, no high availability.

### Afternoon: the relief of a smaller system

Once the branch was gone, the codebase felt lighter. There was no dormant
Postgres adapter, no environment variable for a database URL, no half-migrated
query layer. The app had one storage path and one source of truth. I could explain
the whole thing in a paragraph again.

I spent the afternoon adding a regression test for the exact failure I had seen:
two workers filling the same pending order. The test does not spin up two
workers, because that is not the supported architecture. It asserts that a
single engine fills each pending order once and that the order status changes
before a second fill can see it. The test is a guardrail around the assumption,
not a proof of distributed safety.

### Evening: the cost of a good story

I wanted to write “we evaluated Postgres and chose SQLite for performance.” That
would have been a nicer story. The truth was “we tried Postgres, discovered the
clock and event model were the real problem, and reverted because the app is not
distributed.” The second story is less impressive and more useful.

### End of day

No new feature. One deleted branch. One architecture decision that would save
someone else a weekend.

---

## Day 33 — 12/16/26

### Morning: 30× replay and the cost of a snapshot

At 30× replay, the engine advances roughly thirty bars per second. Each tick
builds a full dashboard snapshot: quotes, leaderboard, forecasts, manual account
and data metadata. The browser receives fewer frames than ticks because the
queue drops old ones, but the server still builds every snapshot. I wanted to
know how much CPU that cost.

I profiled a short run. The simulation loop itself was cheap. Portfolio metrics
and repeated repository queries were the expensive part. The snapshot was doing
work for data that had not changed between ticks: the manual account view, the
equity curve, the full portfolio positions. The dashboard only needed the
summary.

### Afternoon: trimming without changing the contract

I did not change the API shape. I changed what the snapshot builder computed:
summary metrics instead of full position histories, no equity curve, no fields
the dashboard never rendered. The REST endpoints still returned the full views.
The websocket became a render payload, not a database dump.

I measured again. The improvement was modest at 1× and noticeable at 30×. More
importantly, the snapshot became easier to reason about. If a field was in the
frame, some part of the dashboard used it. That is a good rule for a real-time
payload.

### Evening: the optimization I did not make

I considered caching the leaderboard between ticks. It would have helped, but it
would also have introduced invalidation rules around fills, prices and forecast
changes. The app was fast enough without it. I wrote the idea down and did not
build it. At some point, optimization becomes a way to avoid the harder product
questions.

### End of day

A lighter snapshot and a clearer boundary between the render model and the REST
model.

---

## Day 34 — 12/17/26

### Morning: the delta websocket temptation returns

Full snapshots are robust but wasteful. I decided to prototype a delta protocol:
send a full snapshot on connect, then send only changed fields with a sequence
number. On paper it would reduce bandwidth and make the stream feel more
“real-time.” I had already rejected deltas once, but I convinced myself that
sequence numbers and resync would solve the old problems.

I built a small diff function for quotes, leaderboard entries and forecasts. The
first frame looked great. The second frame was smaller. The third frame missed a
nested change because the diff only compared top-level keys. I fixed that. Then
the client applied a delta to a stale base after a reconnect and showed a
leaderboard from two minutes earlier.

### Afternoon: sequence numbers did not save me

The sequence number told the client that it had missed a frame, but the client
had no way to request the missing state except a full resync. I added a resync
request. Then a dropped frame during a fast replay produced a resync every few
seconds, which was more expensive than sending full snapshots in the first place.

I tried compressing the full snapshot instead. That helped bandwidth a little and
added a decompression step on the client. The dashboard is a local demo with eight
tickers, not a market-data terminal. The complexity was not paying for itself.

### Evening: deleting the delta branch

I deleted the branch after two days. The full-snapshot design had been right
the first time. The failure was not in the implementation; it was in the premise
that bandwidth was the bottleneck. It was not. The bottleneck was correctness
under reconnects, and full snapshots solve that by construction.

I felt the familiar frustration of rebuilding a thing I had already rejected. I
wrote a note: “Do not re-litigate a decision unless the constraints have
changed.” The constraints had not changed. I had just gotten bored of the simple
answer.

### End of day

Three days gone. The original architecture survived. I was annoyed, but the
system was still correct.

---

## Day 35 — 12/18/26

### Morning: one more attempt at making deltas work

I went back to the delta branch in the morning because I wanted to salvage
something. I added a server-side ring buffer of the last ten snapshots so a
client could request a specific sequence. The client could then replay the
deltas from its last known sequence. It worked in the happy path. It failed when
the client had been offline for longer than the buffer, which was exactly the
case I cared about.

The fallback was a full snapshot. At that point the protocol had two paths: a
fast delta path for healthy clients and a full-snapshot path for everyone else.
The code had doubled, the tests had doubled, and the failure mode was still
“client shows stale data until the next full frame.” I had recreated the original
problem with more machinery.

### Afternoon: admitting the waste

I closed the branch at 2 p.m. and went for a run. I was angry. Not at the code;
at myself. I had spent two days on a protocol that the app did not need, and I
had known that when I started. The full-snapshot decision was not an accident. It
was a response to real desync bugs. I had ignored my own history because the new
idea was more interesting.

When I got back, I wrote a short post-mortem:

- The problem was not bandwidth. It was state reconciliation.
- The app has one writer and a small payload. Full snapshots are cheap enough.
- The delta protocol added a second source of truth and a resync path.
- The branch was deleted. The lesson was not.

### Evening: restoring the baseline

I checked out the main branch, ran the test suite and loaded the dashboard. It
worked. The full snapshot arrived, the leaderboard updated, the forecasts
appeared. The simple thing was still the correct thing.

I did not touch the websocket code again for the rest of the project.

### End of day

The baseline was restored. The only permanent change was a stronger rule about
not re-opening settled architecture decisions without new evidence.

---

## Day 36 — 12/19/26

### Morning: documenting the non-decision

I wrote an ADR for the websocket: full snapshots, one writer, no deltas. The
consequences were explicit: more bandwidth per frame, no partial updates, and a
client that can recover from any missed frame by taking the next complete
snapshot. For this app, that is the right trade.

I also documented the failed delta experiment in the journal. It would have been
embarrassing to present it as a success. The honest version is more useful: the
team tried a more efficient protocol, hit reconnect desync, and reverted.

### Afternoon: the cost of context switching

I spent the afternoon cleaning up branches, stale environment files and
half-finished notes. There were five branches: React Query, pagination, ML,
Postgres and deltas. All five were dead. Deleting them felt like cleaning out a
closet. I found a few uncommitted changes from experiments that had never been
merged, and I deleted those too.

The main branch was exactly where it had been before the experiments, plus a
handful of documentation and test improvements. That was the correct outcome.

### Evening: a quiet dinner

I had dinner with friends and did not talk about the app. Someone asked what I
had been working on and I said, “A paper-trading simulator.” They asked if it
made money. I said no. They asked why I built it. I said, “Because I wanted to
see whether I could make the numbers honest.” That was the first time I had said
it out loud.

### End of day

The experiments were over. The app was smaller than my ambitions and more
correct than my detours.

---

## Day 37 — 12/20/26

### Morning: the chart on a small screen

The Markets chart looked acceptable on a phone until I opened a stock with a
wide price range. The four grid labels overlapped the line, the right gutter
stole too much of the plot, and the first date label wrapped under the last one.
At desktop width the chart was airy. At 390 px it was a diagram with a line
somewhere inside it.

I tried hiding two of the four grid lines on narrow screens. That helped, but
the remaining labels still collided with the price marker. I tried moving the
labels inside the plot. They covered the line. I tried shortening the dates to
`Jan 2` instead of `Jan 02, 2026`; better, but the start and end labels still
crowded each other when the chart was short.

The final fix was less clever: reduce the right gutter, use three grid lines,
keep the date labels at the very bottom with an 8 px gap, and let the SVG crop
the plot rather than the text. The chart became slightly less precise and much
more readable.

### Afternoon: testing the chart with ugly data

I loaded a synthetic ticker with a huge intraday range and a flat ticker with a
tiny range. The chart handled both, although the flat one looked like a straight
line with a lot of empty space. That was honest. I resisted the urge to add a
minimum y-range because it would exaggerate small moves.

I also checked the empty state. With fewer than two bars, the chart says
“Collecting daily bars…” and does not render axes. That is the correct behavior
for a replay that has not advanced yet.

### Evening: a small design review

Nina looked at the mobile chart and said, “It looks like a chart now.” That was
the whole review. I took the win.

### End of day

A responsive chart that did not lie about the data. No new interaction features.

---

## Day 38 — 12/21/26

### Morning: the market was closed but the app disagreed

A user opened the app on a market holiday and saw **Live · market open**. The
backend's market-hours check only knew about weekdays and the 09:30–16:00 New
York window. It did not know about holidays, and it did not know about early
closes. Yahoo returned a quote timestamp that was fresh enough to pass the
staleness check, so the app believed the market was trading.

The dashboard then created a forming bar from stale quotes and allowed manual
orders to queue as if they would fill on the next poll. They would not fill until
the next real session. The user saw a live session that was not live.

### Afternoon: the holiday calendar rabbit hole

I looked for a simple holiday calendar. There are libraries, exchange calendars
and APIs. Each one added a dependency or a maintenance burden. I tried a small
hard-coded list of US market holidays for the current year. It worked for the
demo dates and would be wrong next year. I tried a rule-based calculation for
the common holidays and immediately got Thanksgiving and Good Friday wrong.

I stopped. The correct fix for this demo was not a perfect exchange calendar; it
was to make the limitation explicit and to tighten the quote-freshness check.
If the latest quote was more than 30 minutes old, the app should not claim the
market was open, even if the wall clock said it was a weekday.

### Evening: the honest version

I added a note to the README: live mode uses a weekday/time check and quote
freshness, not an exchange holiday calendar. On a holiday with a stale quote,
the app should show the market as closed. If Yahoo returns a misleadingly fresh
timestamp, the app may briefly disagree. That is a known limitation.

I did not ship the half-correct holiday list. A wrong calendar would have been
worse than an honest approximation.

### End of day

The app did not become holiday-perfect. It became less confident in the wrong
places, which was the right direction.

---

## Day 39 — 12/22/26

### Morning: Yahoo had a bad day

Yahoo returned 502s for several tickers in a row. The live poll retried, then
failed. The dashboard kept the last known prices and showed the stale data note.
No crash. No blank screen. The fallback worked exactly as designed.

The frustrating part was the uncertainty. A 502 could mean a temporary gateway
problem, a rate limit in disguise, or a ticker-specific failure. The retry helper
treated all three the same. I added a log line with the ticker and the final
error so the next incident would be easier to diagnose.

### Afternoon: the stale cache question

A user asked whether the live dashboard was “real” during the outage. The answer
was: the last known prices are real, but they are not current. The UI said
“last close” when the market was closed, but during an open-market outage it
still said “live” because the mode was live. The data was stale.

I wanted the Markets header to say **last quote** when the live poll had an
error, regardless of market state. The existing data note already carried the
poll status, so I did not add another label that could drift out of sync with
the source. The forecast tab kept the last calls; I did not regenerate them
from stale prices.

### Evening: resilience is not the same as freshness

The app stayed up through the outage, which felt like a win. But “up” and
“fresh” are different claims. I wrote the distinction into the README and the
data note: live mode can display the last known quote when Yahoo is unavailable;
check the poll status before treating it as current.

### End of day

No new data source. A more honest label and a better log line.

---

## Day 40 — 12/23/26

### Morning: the database that survived a deploy

I attached a Render disk to a test service and set `DB_PATH` to a file on it.
Then I deployed, placed a manual order, forced a redeploy, and checked whether
the order and the account history were still there. They were. After a month of
documenting the ephemeral-filesystem limitation, seeing persistence work was
oddly emotional. The demo could have a memory.

The disk introduced a new operational question: backups. I tested copying the
database while the service was stopped, then while it was running. The stopped
copy was consistent. The running copy needed the WAL checkpoint first. I wrote
the backup procedure down with the three-file rule and a note that a single
`.db` copy is not a backup.

### Afternoon: the cost of persistence

A disk is not free. I had to decide whether the demo justified one. For a public
showcase, a reset on deploy is acceptable if the UI says so. For a competition
that runs for weeks, a reset is a broken promise. I documented both modes:
ephemeral demo, persistent deployment. The code did not need a flag; the
environment did.

I also checked what happens when the disk fills up. There is no retention job.
The database is small today, but a long-running live service writes snapshots
forever. I added a backlog item for retention and a note that the current demo
does not prune old snapshots.

### Evening: a quiet sense of durability

The app could now survive a redeploy with its history intact. That was not a
feature a user would notice on a normal day. It was the difference between a
toy and a record.

### End of day

Persistence worked. The backup procedure existed. The limitations were written
down.

---

## Day 41 — 12/24/26

### Morning: dependency audit

I ran the dependency audit I had been postponing. The backend pins were old
enough to be boring and new enough to install. The frontend lockfile was clean.
There were no critical vulnerabilities that required an emergency upgrade.

I was tempted to upgrade everything anyway. Fresh dependencies feel like
progress. Then I remembered the Python 3.14 incident: a “minor” runtime change
had turned a wheel install into a Rust build. I upgraded nothing that was not
security-critical and wrote down the versions that were known to work.

### Afternoon: the Python pin is part of the product

I added a note to the deployment docs that `PYTHON_VERSION=3.12.3` is not a
suggestion. It is part of the build contract. The pinned `pydantic-core` version
does not have a wheel for every newer interpreter, and the failure mode is a
source build that looks like a compiler problem. A future maintainer should not
have to rediscover that.

I also checked that the local virtual environment and the deployment used the
same Python minor version. They did. That sounds obvious. It is the kind of
obvious thing that breaks a deploy at 11 p.m.

### Evening: no upgrade, no incident

I closed the laptop without changing a dependency. It felt anticlimactic, which
was the goal. A boring dependency day is a good dependency day.

### End of day

No new packages. A version contract written down.

---

## Day 42 — 12/25/26

### Morning: Christmas, and the app did not need me

I opened the dashboard once, mostly out of habit. It was live, the replay was
paused, and the leaderboard showed the same accounts as yesterday. Nothing was
on fire. I closed the tab.

For most of the day I did not think about the project. That was healthy. The
previous month had trained me to treat every quiet moment as a bug to investigate.
A demo that can survive a holiday without attention is doing its job.

### Afternoon: reading old notes

I reread the first Figma handoff note. It said “a forecast is an estimate, never
a guarantee.” I had written that on 11/10, before any code. The final UI said
almost the same thing. That continuity made me happy. The project had changed a
lot, but the important sentence had survived.

I also reread the sticky note with the replay sequence. It was still accurate.
The accounting identity was still accurate. The architecture decisions that
mattered were the ones we had written down early.

### Evening: a small gratitude

I sent Nina a message thanking her for the prototype review that moved Forecasts
to the left. She replied with a screenshot of the current app and a single word:
“Good.” It was the best code review I got all month.

### End of day

No commits. A quiet holiday and a reminder that the app is not a person.

---

## Day 43 — 12/26/26

### Morning: the user who wanted fewer numbers

A user wrote that the Forecasts tab was “too much information.” They liked the
top call and the per-AI ranking, but the price and per-share columns felt like
noise. I resisted the urge to remove them. Another user had specifically asked
for the per-share value because a percentage alone did not tell them what a
share would do.

The answer was not fewer numbers; it was better grouping. I moved the price and
per-share estimate onto a secondary line with smaller type and a clear label.
The primary line became ticker, direction and percentage. The information was
still there, but the eye could choose whether to read it.

### Afternoon: the manual account again

Another user asked why their equity did not change when they bought a stock.
The answer was that buying converts cash into a position; equity stays roughly
the same until the price moves. The account panel showed cash and equity but did
not explain the relationship. I drafted a short caption for the account values:
“Buying moves cash into positions; equity changes with prices.” I added it to the
backlog rather than pushing another line into the ticket before the next review.
The explanation went into the README immediately.

### Evening: small feedback, small fixes

Launch-week feedback had been dramatic: black screens, CORS, missing data.
Month-two feedback was quieter: “I did not understand this number,” “this label
is confusing,” “the row is too busy.” The work was less exciting and more
useful. The product was becoming understandable to people who had not built it.

### End of day

A clearer forecast row and a clearer account caption. No architecture changes.
No new dependencies.

---

## Day 44 — 12/27/26

### Morning: the Next.js impulse

I had been reading about server-rendered React and convinced myself the
dashboard would benefit from Next.js. Better initial load, API routes in the
same project, a cleaner deployment story. I created a branch, scaffolded a new
app, and started porting the shell.

The first problem was the static host. The current deployment is a Vite SPA
uploaded to a static site. A Next.js app with server rendering needs a Node
runtime or a Workers-compatible adapter. I was not just changing the framework;
I was changing the hosting model, the build pipeline and the API boundary.

The second problem was the WebSocket. The app depends on a persistent socket to
a separate FastAPI backend. Next.js did not make that simpler. It added a second
server and a second set of environment variables.

### Afternoon: porting the easy parts

I ported the header, tabs and leaderboard. It looked fine. Then I hit the API
client. The existing client uses `VITE_API_BASE`; the Next app uses a different
public environment convention. I started rewriting the client, then realized I
would also need to rewrite the WebSocket hook, the static asset paths and the
deployment docs.

I had a working shell and no data. The original app had data. This was not a
refactor; it was a parallel product with a different hosting contract.

### Evening: deleting the branch

I closed the branch before dinner. The impulse had cost me a day. I wrote a note:
“Do not change the rendering model to solve a problem you do not have.” The
dashboard loads fast enough as a static SPA. The API is separate by design. Next.js
would have added complexity without improving the core experience.

### End of day

One day gone. The Vite app was still the right app.

---

## Day 45 — 12/28/26

### Morning: cleaning up the SSR branch

I deleted the Next.js branch and the generated lockfile. I checked the main
branch for stray files: none. I rebuilt the Vite app to prove the toolchain was
untouched. It was.

I wrote an ADR: **static SPA + separate FastAPI backend**. The decision was
driven by deployment simplicity, the existing static host, and the fact that the
app has no SEO or server-rendering requirement. The consequences: no server-side
rendering, no API routes in the frontend, and a build-time API URL.

### Afternoon: the cost of framework tourism

I added up the time spent on experiments: React Query, pagination, ML, Postgres,
deltas, Next.js. Some were one day, some were three. The total was more than a
week of work that never shipped. I did not regret all of it; the Postgres and
delta experiments produced architecture decisions that made the README stronger.
But I could have time-boxed them better.

I wrote a rule for future experiments: one day to prove the core assumption,
then stop. If the core assumption cannot be proven in a day, it is a project,
not an experiment.

### Evening: a smaller main branch

The main branch had no new features from the experiments, but it had better
documentation, a few more tests and a clearer architecture. That was enough.

### End of day

The framework detour was over. The app was still small, static and understandable.

---

## Day 46 — 12/29/26

### Morning: the auth prototype

The security review had made me uncomfortable about the public reset and order
endpoints. I decided to prototype authentication. Nothing fancy: a single admin
login, a session cookie, and protected mutation routes. It sounded like a
weekend project.

It was not. The app has no user table, no email service, no password reset flow
and no concept of ownership. Adding a login screen would have protected the
endpoints but not answered the real question: whose portfolio is this? The
manual account is global. A second user would share it.

### Afternoon: the scope explosion

I listed the work: user table, password hashing, session storage, CSRF
protection, login/logout UI, protected routes, per-user portfolios, migration of
the existing manual account, and a story for what happens to the AI competition
when there are multiple users. That was a multi-week project. A login screen
without those pieces would have been security theater.

I stopped before writing the auth flow. I wrote a note: “The demo is
single-tenant by design. Protect it at the network layer or accept that it is
public.” That was less satisfying than a login form and more honest.

### Evening: the wrong kind of progress

I felt deflated. I wanted to fix the security gap, and the correct fix was bigger
than the project. I added the limitation to the README again, with a clearer
warning: anyone with the URL can reset the demo. If that matters, put it behind
a private network or add a real auth layer.

### End of day

No auth. A clearer boundary around what the demo is.

---

## Day 47 — 12/30/26

### Morning: the rate limiter

The next security impulse was rate limiting. A simple in-memory token bucket
would stop accidental request floods and make the manual order endpoint less
abusable. I built a small middleware prototype: per-IP buckets, a 60-request
limit, a 429 response.

It worked in a single process. Then I remembered the architecture decision: one
process is the supported deployment. An in-memory limiter is consistent with
that. It would reset on restart and would not protect a multi-instance
deployment, but neither would the rest of the app.

### Afternoon: testing the limiter

I fired a hundred requests at the order endpoint and watched the 429s appear. The
frontend handled the error as a generic failure, which was not great. I added a
message for “too many requests” and a short retry hint.

Then I looked at the actual risk. The app is a demo with no real money. The most
likely abuse is a script resetting the leaderboard, not a sophisticated flood.
A rate limiter would slow that down, but it would not stop it. The real fix was
still authentication or network isolation.

### Evening: keeping the prototype?

I kept the limiter on the branch but did not merge it. It added a dependency-free
middleware, a new error path, and a configuration value. It also created a false
sense of security. I decided the demo did not need it yet. I wrote the idea into
the backlog and moved on.

### End of day

A prototype, a test, and a decision not to ship. The app remained a demo with
documented risks.

---

## Day 48 — 12/31/26

### Morning: end-of-year freeze

I declared a freeze for the last day of the year. No new features, no
experiments, no branch cleanups that could break the main build. I ran the test
suite, rebuilt the frontend and loaded the app. Everything worked.

I checked the production URL one more time. The dashboard loaded, the forecast
tab showed calls, the leaderboard ranked the accounts, and the WebSocket
connected. The year ended with the app in a stable state.

### Afternoon: the annual-review feeling

I read through the journal and felt the usual end-of-year mix of pride and
embarrassment. The black screen, the Python 3.14 failure, the Postgres detour,
the delta protocol, the ML experiment. So much time spent learning what not to
do. The working app was the small visible part of a much larger pile of deleted
branches.

I wrote a short list of what I was grateful for: tests that caught accounting
bugs, a designer who said “this is three products,” a friend who asked why his
account was not at the top, and a deployment checklist that eventually worked.

### Evening: no deploy at midnight

I did not deploy at midnight. Nothing needed to change at midnight. I closed the
laptop, watched the city lights, and let the year end without a release.

### End of day

Stable. Quiet. Enough.

---

## Day 49 — 01/01/27

### Morning: a new year and an old app

The first day of the year was quiet. I opened the dashboard, saw the replay
paused at the end of the cached data, and closed it. No deploy. No bug. No
resolution. I made coffee and sat by the window for a while.

I thought about how strange it is that software becomes real through repetition.
A month ago the app was a Figma file and a set of opinions. Now it was a URL
with a database, a test suite and a list of known limitations. The transition
did not feel like a single moment; it felt like a hundred small mornings.

### Afternoon: the list of unfinished things

I made a list of everything I would do with another month: authentication,
per-user portfolios, forecast accuracy scoring, a real news feed, retention for
snapshots, a holiday calendar, a connection indicator, pagination, better mobile
tables. It was a good list. It was also proof that the project could absorb
infinite time if I let it.

I drew a line under the list and wrote: “This version is done when the core loop
is honest and documented.” It was. The list could wait.

### Evening: no journal guilt

I did not feel guilty for not coding. That was new. For most of the project, a
day without a commit felt like a day wasted. On New Year's Day, a day without a
commit felt like a day.

### End of day

A quiet start to the final week.

---

## Day 50 — 01/02/27

### Morning: writing the architecture record

I wrote the architecture decision records I had been carrying in my head:

- **One process, one clock.** SQLite and the in-process event manager are
  deliberate. Multiple workers would duplicate decisions and split the websocket
  stream.
- **Full snapshots.** Deltas were tried and reverted. Reconnect correctness is
  more important than bandwidth for eight tickers.
- **A static SPA.** Next.js was tried and reverted. The app has no server-render
  requirement, and the separate FastAPI backend is the boundary.
- **A transparent forecast heuristic.** The ML experiment was rejected because
  it was less accurate out of sample and impossible to explain.
- **Single-tenant demo.** Authentication is a product project, not a login form.
  The public endpoints are a documented risk.

Writing the decisions down was strangely emotional. Each one represented a
branch I had deleted, a day or a week I could not get back, and a belief I had
changed my mind about.

### Afternoon: the value of a written no

The ADRs made the “no” decisions visible. A future maintainer could see that
Postgres and deltas were considered, not overlooked. That is more useful than a
clean architecture diagram that pretends the alternatives never existed.

I added links from the README to the journal and the ADR notes. The docs now
told the happy path and the detours.

### Evening: a lighter head

Once the decisions were written down, I stopped rehearsing them in the shower.
That is the practical benefit of documentation: it offloads the arguments.

### End of day

Five decisions. Five deleted branches. A clearer system.

---

## Day 51 — 01/03/27

### Morning: regression pass

I ran the backend tests, the TypeScript build and the production bundle. I
loaded every tab, checked the empty states, placed a manual order, watched it
fill, switched modes, reset and reloaded. I checked the WebSocket reconnect by
restarting the backend while the page was open. It recovered.

The regression pass found one documentation bug and no code bugs. The README
still said the forecast rows showed “confidence” without explaining that it was
signal confidence, not probability of profit. I fixed the sentence.

### Afternoon: browser and mobile checks

I checked the dashboard at 390 px, 768 px, 1120 px and 1440 px. The leaderboard
table held its columns, the forecast rows stacked, the chart labels stayed
inside the card. The trading buttons were reachable without scrolling past the
positions table. None of it was perfect, but all of it was usable.

I checked the served production HTML and confirmed the hashed bundle name
matched the build. I checked the CORS preflight and the `wss://` socket URL. The
deployment checklist had become a habit.

### Evening: the satisfaction of a boring test run

The test suite passed. The build passed. The browser worked. I felt the quiet
satisfaction of a system that had stopped surprising me. Surprises are for
launches. Boring is for maintenance.

### End of day

No feature changes. One documentation correction. A stable app.

---

## Day 52 — 01/04/27

### Morning: the final deploy

I deployed the final build on a weekday morning, not at midnight. The service
was awake, the logs were open, and I had time to react if something failed. The
build used Python 3.12.3, the CORS origin was exact, the static upload contained
the dist contents, the SPA rewrite was in place, and the WebSocket URL used
`wss://`.

The deploy succeeded. I watched the dashboard for ten minutes. The replay
advanced, orders filled, forecasts updated, the leaderboard moved. Nothing
dramatic happened. I closed the logs.

### Afternoon: the README read-through

I read the README as a stranger. It explained how to run the app, what every tab
does, how the forecast is calculated, why orders fill later, how to deploy, and
what the known limitations are. It also linked to the journal, which explained
why the app looks the way it does and why some obvious ideas were rejected.

I found two stale details: a default value that had changed and a path that
pointed to an old build artifact. I fixed them. Documentation is never finished;
it is only current.

### Evening: the last screenshot

I took a screenshot of the dashboard for the project page. The leaderboard was
ranked, the forecast tab was populated, the market list was green, and the
manual account was visible. It looked like a product. I did not edit the
screenshot to hide the “not investment advice” note. That note was part of the
product.

### End of day

The final build was live. The docs matched the build. The screenshot was honest.

---

## Day 53 — 01/05/27

### Morning: the entry I thought was last

I opened the journal to write what I thought would be the final entry and
realized I had been keeping it for almost two months. It started with a Figma
file and no repository. It had reached 53 entries, five unlogged rest days, a
pile of deleted branches and a much better understanding of what “done” means.

I read the first entry again. I had written: “No repository. No backend. No
frontend. Just a design direction.” That version of me was impatient and a little
scared. The current version was tired and a little proud. Both were necessary.

### Afternoon: what the project taught me

The technical lessons are in the appendix. The human lessons are harder to
write down:

- Design first is not slow. It is the fastest way to avoid building the wrong
  thing twice.
- A deleted branch is not a failure if it produces a decision.
- A fallback can hide a failure. Resilience without visibility is its own risk.
- A forecast is a product claim, not just a number. The wording matters as much
  as the formula.
- The most dangerous bugs are the ones that make the numbers look better.
- A boring deployment checklist is a form of care.

I also learned that I am not good at time-boxing experiments when I am curious.
The Postgres and delta detours were interesting enough that I ignored my own
rules. Writing that down was more useful than pretending I had been disciplined.

### Evening: closing the laptop

I closed the laptop at 4:50 p.m. The app was live. The journal looked complete.
The remaining backlog was real but not urgent. I did not feel the urge to check
the logs one more time.

The project is a paper-trading simulator. It is also a record of learning when
to stop, when to delete, and when to admit that a simple answer is the right one.
I am glad I built it. I am glad the main build is finished.

### End of the main build

---

## Day 54 — 01/06/27

### Morning: “the live thing is not doing anything”

The message arrived before I had finished my coffee: “The live thing I don’t
think is working really, because Render is on the free plan and goes off without
activity, so it’s not actually making forecasts and stock transactions.”

My first reaction was defensive. The live loop worked. I had tested it. Then I
opened the Render dashboard and felt the floor tilt. The service had been asleep
for most of the night. The logs showed a clean shutdown after an idle period and
a cold start when the user opened the page. There were no errors because nothing
had been running to produce one.

The engine was fine. The service was not awake.

### Afternoon: the difference between “live” and “always on”

I had been thinking about live mode as a property of the code. If `SIM_MODE=live`
and the market was open, the poll ran, the agents decided, and orders filled.
That is true only while the process is alive. A free Render web service sleeps
after roughly fifteen minutes without incoming traffic. When it sleeps, the
background clock stops. No requests, no polls, no forecasts, no fills.

The dashboard’s WebSocket did not save it. An open tab may or may not count as
traffic for long enough, depending on the platform and the browser tab’s state.
A closed tab definitely does not. The user had done the most natural thing in
the world: closed the laptop and expected the live simulation to continue.

I felt embarrassed. I had documented the free-tier filesystem reset but not the
free-tier sleep. The app looked live, so I had let myself believe it was live. It
was live only when someone was watching.

### Evening: two wake-up paths

I added a small frontend heartbeat. While the dashboard is open, the stream hook
calls `/api/health` every four minutes. It is not a data refresh; the WebSocket
still carries snapshots. It is a deliberate request to keep the instance from
idling out.

For the no-browser case, I added `.github/workflows/keep-alive.yml`. It runs
every five minutes on GitHub Actions and pings the same health endpoint. That is
an external clock the app does not have to own. It can also be triggered
manually from the Actions tab.

Neither solution is perfect. GitHub Actions schedules can be delayed, and
scheduled workflows are disabled after long repository inactivity. A free
instance can still sleep if the pinger fails. For a demo, the combination is
good enough to keep the simulation alive most of the time. For reliable 24/7
trading, the honest answer is a paid instance or an external uptime monitor.

I also clarified the behavior after a wake-up: the live clock resumes from the
current time. It does not replay the hours it missed. There is no backfill of
forecasts or fills for the sleeping period. That is the correct behavior for a
live simulation, but it means “live” cannot mean “continuous” on a free tier.

### Late evening: the engine was never the bug

I ran the live mode locally one more time with the market open and watched a
decision, a forecast batch and a fill. Everything worked. The only thing that
had been broken was the assumption that a sleeping service is still running.

I added a note to the README, a new entry to the journal, and a small apology to
the user. “You were right,” I wrote. “The engine was fine. The host was asleep.”
It was the least dramatic bug of the project and the most important operational
lesson: an app is not live just because its code says live.

### End of day

The heartbeat and the scheduled ping were in place. The limitation was written
down. The engine still could not run while the computer was off, but at least
now something else was knocking on the door.

---

## Day 55 — 01/07/27

### Morning: showing the model its own field of view

The request was two things: show how far back the models look, and add a button
that makes a prediction immediately instead of waiting for the clock.

I wrote the plan on a sticky note before opening the editor: expose the lookback
windows from the engine, render them above the calls, add a record-only
prediction path to the API, wire a button to it, and write a test that proves the
button does not trade. That was the whole plan. No new model, no new data
source, no redesign.

The honest answer to “how far back” is shorter than people expect. The price
model uses a 20-session slow average and 10 sessions of momentum. The news model
looks at the last five sessions. Volatility uses 20 sessions, and the forecast
horizon is five sessions. The context loads up to 120 bars so the history
endpoint and debugging have room, but the models only read their own windows.
Calling them neural networks would be generous; they are three transparent
heuristics with fixed inputs.

### Midday: separating prediction from trading

The code made this easier than I expected. `BaseAgent.step()` did three jobs:
evaluate the signals, record the top five forecasts, and turn the signals into
order intents. I split out `_collect_signals()` and added
`record_forecasts()`. `CompetitionManager` got a shared `_context()` helper and a
`run_forecasts()` method that calls the record-only path for every agent. The
new route is `POST /api/market/forecasts/refresh`.

The one thing I had to be careful about was not taking a shortcut. If the button
had called `step()` and thrown away the returned intents, the forecasts would
have looked right but every press would have queued trades. That is exactly the
kind of bug that survives a happy-path test and surprises someone later. I kept
the manual path separate and added a test that checks the order count before and
after a refresh.

### Afternoon: a day without a fire

The backend tests passed on the first full run: 53 of them. The frontend
typecheck and production build passed too. I kept waiting for a red line or a
stack trace. Nothing came.

The only friction was layout. The five lookback labels and the button fought for
the same row on a narrow screen, so I moved the button into its own actions
group and let the labels wrap underneath. That was the whole afternoon problem.
I am trying not to turn every entry into a postmortem; some days are a clean
diff and a green test run, and that is allowed.

I still checked the awkward cases: paused, after hours, and an early bar without
enough history. The button returns fewer calls when there is not enough data.
In live mode it uses the latest visible bar, which may be the last poll rather
than a brand-new quote. After hours it uses the last session. It does not invent
bars to make the screen look busy.

I also worried the button would read like a “make money now” control. The copy
says it refreshes calls without placing orders, and the test enforces that. A
forecast is still a forecast, not a trade.

### Evening: the honest version

The feature changes how the app feels. Before, predictions appeared when the
clock decided. Now you can ask for them. That is better for a demo and better
when I am debugging, but it could also encourage checking the tab too often and
treating five ranked calls as a stronger signal than they are. The models are
still looking at a fixed window of the past. The button makes them answer
sooner; it does not make them see further.

There is also a deployment gap I do not want to hide. The code is committed and
pushed, but the live dashboard and backend still have to be rebuilt from this
commit. If the Render service deploys from a separate backend repository, these
changes have to go there too. The endpoint works locally; I am not going to
claim the button works in production until it has been deployed.

I closed the laptop at 6:10 p.m. and did some homework. No fire, no dramatic
last-minute fix, no lesson about resilience. Just a small feature that made the
model explain its inputs and let me ask for an answer without waiting. Some days
are like that.

### End of day

The lookbacks were visible, the button was wired to a record-only path, and the
tests proved it did not trade. The day was done.

---

## Day 56 — 01/08/27

### Morning: “the entire screen is black again”

The message was short and familiar: the entire screen was black again. I had
just finished the forecast accuracy scorecard, so my first assumption was that I
had broken the frontend. A bad hook, a missing field, a component that crashed
before React could paint anything — those all look like a black page.

I opened the deployed URL instead of guessing. The page title loaded. The body
was empty. That narrowed it down immediately: the HTML was arriving, but the
application bundle was not running.

### Midday: the console knew before I did

The browser console had two errors. The important one said the module script
failed because the server responded with an empty MIME type. The network tab
showed the reason: the page was requesting `/src/main.tsx` and getting a 200.
The favicon was a 404. The served HTML contained:

```html
<script type="module" src="/src/main.tsx"></script>
```

That is the Vite development entry point. A static host cannot compile TSX. The
browser downloaded source code as a module, refused to execute it, and left the
empty `#root` div sitting on a dark background. It looked like a frontend
failure. It was an upload failure.

The built files were fine. `frontend/dist/index.html` referenced the hashed
bundle and stylesheet:

```html
<script type="module" crossorigin src="/assets/index-Do3xymQj.js"></script>
<link rel="stylesheet" crossorigin href="/assets/index-Bkrb0fWz.css">
```

The scorecard was in that bundle. None of it reached the browser because the
host was publishing the source folder instead of the build output.

### Afternoon: the same mistake, one more time

I have made this mistake before. I wrote the troubleshooting note. I knew that
the deployable artifact is the **contents** of `frontend/dist`, not the
`frontend` folder. And still, when I packaged the updated frontend and uploaded
it, the root of the site ended up with the development `index.html` while the
real build sat one level deeper under `dist`.

The frustrating part is that nothing about the application was broken. The
backend tests were green. The frontend build had passed. The scorecard existed
in the bundle. The only broken thing was the handoff between the build output
and the static host.

I checked the artifact again to be sure:

- `frontend/dist/index.html` references `/assets/index-*.js`.
- `frontend/dist/assets/` contains the JavaScript and CSS.
- `frontend/index.html` references `/src/main.tsx`.

Those two files are supposed to be different. On the host, they had become the
same file at the publish root.

### Evening: the fix is boring, which is the point

The fix is not a code change. Publish the contents of `frontend/dist` so that
the site root contains:

```text
index.html
assets/index-*.js
assets/index-*.css
favicon.svg
```

Do not publish the `frontend` folder. Do not publish `frontend/index.html`.
After uploading, open the page source and confirm the script tag points at
`/assets/`, not `/src/main.tsx`. Then hard-refresh once to clear the old HTML.
The SPA rewrite still needs to send unknown routes back to `index.html`.

I could confirm the diagnosis and the correct artifact from here, but I could
not reach the host's file manager, so I did not pretend the production site was
fixed. I wrote the steps down instead of relying on memory. The next upload
should be one folder shallower than the last one.

### End of day

The application was fine. The deployment was serving the wrong folder, and the
black screen was the browser refusing to compile source it should never have
received. It was not a clever bug. It was the same boring handoff mistake, and
boring mistakes still count.

### End of journal

---

## Appendix: architecture decisions and abandoned experiments

These are the decisions that survived the experiments. Each one has a cost and a
reason, and each one was easier to defend after trying the alternative.

| Decision | Why it stayed | Cost |
| --- | --- | --- |
| One backend process, one clock | Correctness depends on a single scheduler; multiple workers duplicated fills and split the websocket stream | No horizontal scaling |
| SQLite with WAL | No external service, easy to inspect, fast enough for four portfolios | Ephemeral on free hosting; single-writer deployment |
| Full websocket snapshots | Reconnects recover by taking the next complete frame; no desync protocol | More bandwidth per frame |
| Static Vite SPA + separate FastAPI | Simple static hosting and a clean API boundary; no server-render requirement | Build-time API URL; no SEO/SSR |
| Transparent forecast heuristic | Explainable, deterministic, no training dependency; the ML alternative lost out of sample | Not adaptive; cannot learn new regimes |
| Single-tenant demo | Authentication without per-user ownership would be security theater | Public reset/order endpoints; documented risk |
| Percentage-ranked forecasts | Comparable across stocks; per-share value is shown as context | Not ranked by position-sized dollars |

The abandoned experiments are part of the architecture record because they
explain why the simple version exists. The time estimates are rough, and none of
them include the cleanup that followed.

| Experiment | Time spent | Why it was abandoned |
| --- | --- | --- |
| TanStack Query cache | ~2 days | Duplicated the websocket snapshot and produced stale/fresh flicker |
| Cursor pagination for activity | ~4 hours | The UI intentionally shows twelve rows; the mechanism solved no user problem |
| Sparklines in forecast rows | ~1 hour | Cluttered the row and competed with the percentage |
| ML replacement for forecasts | ~2 days | Leakage and walk-forward tests showed no reliable edge; unexplainable output |
| Postgres + multiple workers | ~2 days | Clock, order filling and event fan-out were the real distributed problem |
| Delta websocket protocol | ~2 days | Reconnect desync and resync machinery were worse than full snapshots |
| Next.js server rendering | ~1 day | Changed hosting, API boundary and env model for no product benefit |
| Auth prototype | ~1 day | A login form without users, ownership and sessions was not a security fix |
| In-memory rate limiter | ~1 day | Consistent only with single-instance deployment; created false confidence |
| Exchange holiday calendar | ~1 day | Half-correct calendar was worse than an honest freshness limitation |

The total is roughly two working weeks that never shipped. That sounds bad until
it is compared with the alternative: shipping a distributed, cached, ML-driven
system that nobody could explain and that broke in ways the tests did not cover.
The deleted branches were tuition, not progress, and the journal keeps the
receipts.

---

## Appendix: recurring bug patterns

| Pattern | Typical symptom | Root cause | Fix |
| --- | --- | --- | --- |
| Look-ahead | Implausible returns | Decision price used as fill price | Next-bar open fills |
| Phantom equity | Short raises equity twice | Short treated as positive asset | Signed positions everywhere |
| Fee leakage | AI always beats the benchmark | Fees/borrow omitted | Per-side fees + daily borrow |
| CORS wall | Works via Vite proxy, fails online | Exact origin mismatch | Exact `CORS_ORIGINS`, preflight test |
| Wrong API | Browser calls old host | Build-time env baked into bundle | Rebuild after URL change |
| Black screen | 200 HTML, empty page | Source `index.html` uploaded | Upload `dist` contents |
| Static 404 | Refresh/deep link fails | No SPA rewrite | Rewrite all paths to `index.html` |
| Socket loop | Console flooded, stale data | Immediate reconnect | 2.5 s retry + REST fallback |
| Duplicate trades | Flickering leaderboard | Multiple workers/engines | One process; document scaling limits |
| Database reset | Accounts back at $10k | Ephemeral Render filesystem | Persistent disk + `DB_PATH` |
| Slow cold start | Health check delayed | First Yahoo download | SQLite cache, fewer refreshes |
| Forecast confusion | `-6%` read as a loss | Direction/label ambiguity | Rise/drop labels, short note, disclaimer |
| Hidden socket failure | Page looks alive but is polling | Fallback masks dead stream | Connection indicator and monitoring |
