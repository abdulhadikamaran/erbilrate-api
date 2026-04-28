# Architecture Reference
## Erbil USD/IQD Market Rate Platform

| Field | Value |
|---|---|
| **Status** | ✅ Production |
| **Last Updated** | 2026-04-27 |
| **Stack** | Python / FastAPI / PostgreSQL / Telethon / Vanilla JS PWA |

---

## 1. Project Structure

```
usd/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, lifespan, static file serving
│   ├── config.py               # Settings loaded from .env, all constants
│   ├── database.py             # asyncpg connection pool, schema, queries
│   ├── models.py               # Pydantic response models
│   ├── ws_manager.py           # WebSocket connection manager + broadcaster
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py           # All REST API route handlers
│   ├── telegram/
│   │   ├── __init__.py
│   │   ├── fetcher.py          # Telethon session client, message fetching
│   │   └── parser.py           # Multi-layer parser, filter, validate
│   └── scheduler/
│       ├── __init__.py
│       └── jobs.py             # Background loop: fetch → parse → store → broadcast
│
├── scripts/
│   ├── auth.py                 # One-time Telethon session auth (run manually)
│   ├── recover_missed.py       # Utility: backfill missed messages manually
│   ├── extract_session.py      # Generates TELEGRAM_SESSION_STRING (run once)
│   └── fix_firewall.bat        # Windows dev utility: open required ports
│
├── static/
│   ├── index.html              # Single-page PWA shell
│   ├── js/
│   │   ├── app.js              # Main controller: init, WS listener, rate display
│   │   ├── converter.js        # Real-time currency converter logic
│   │   ├── chart.js            # Chart.js rendering (today + history tabs)
│   │   ├── cache.js            # localStorage cache manager
│   │   ├── i18n.js             # Kurdish / English translation system
│   │   └── tailwindcss.js      # Tailwind CSS runtime (bundled)
│   ├── icons/                  # PWA icons (192px, 512px)
│   └── flags/                  # Flag images for UI
│
├── data/
│   └── .gitkeep                # Placeholder (DB is PostgreSQL, not file-based)
│
├── docs/                       # This documentation directory
├── extract_session.py          # One-time utility: generate TELEGRAM_SESSION_STRING
├── .env                        # Secrets (gitignored)
├── .env.example                # Template for required env vars
├── requirements.txt
└── README.md
```

---

## 2. Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.10+ | |
| Web Framework | FastAPI | Async-native, ASGI |
| ASGI Server | Uvicorn | Production deployment |
| Telegram Client | Telethon | Full Client API (not Bot API) — uses session string |
| Database | PostgreSQL | Via asyncpg connection pool |
| Real-Time | WebSockets | Native FastAPI WS, managed by `ws_manager.py` |
| Frontend | Vanilla JS + HTML | ES Modules, no framework |
| Styling | Tailwind CSS v3 | Bundled locally (`tailwindcss.js`) |
| Charts | Chart.js (CDN) | Line charts for today + history |
| PWA | Service Worker + Manifest | Offline support, installable |
| Config | python-dotenv | Secrets from `.env` |
| Hosting | Render.com | PaaS, single web service |

---

## 3. Module Responsibilities

| Module | Responsibility |
|---|---|
| `app/main.py` | App creation, lifespan (DB init, scheduler start/stop), CORS, static file mounting |
| `app/config.py` | Loads `.env`, defines all keywords, thresholds, and constants as a `Settings` singleton |
| `app/database.py` | asyncpg pool management, schema creation, all SQL queries. **No SQL in other modules.** |
| `app/models.py` | Pydantic models for all API response shapes |
| `app/ws_manager.py` | Tracks connected WebSocket clients; `broadcast()` pushes new rate to all of them |
| `app/api/routes.py` | Thin route handlers: validate input → call DB/cache → return model |
| `app/telegram/fetcher.py` | Telethon session management; `fetch_new_messages()` and `fetch_initial_messages()` |
| `app/telegram/parser.py` | Full parse pipeline: exclude → line scan → regex Layer 1/2 → validate → anomaly check |
| `app/scheduler/jobs.py` | Infinite async loop (5 min); orchestrates fetch → parse → store → WS broadcast |

---

## 4. Data Flow

### 4.1 Background Ingest Loop (Every 5 Minutes)

```
asyncio background task (start_scheduler)
    │
    ├── 1. fetcher.fetch_new_messages(last_msg_id, limit=20)
    │        └── Telethon → @iraqborsa → returns list[Message]
    │
    ├── 2. For each message (oldest first):
    │        └── parser.parse_message(text, msg_id, last_average)
    │              ├── Exclude: gold keywords → skip entire message
    │              ├── Line scan: هەولێر + (پێنجی or سوور) required
    │              ├── Regex Layer 1: $100=XXX,XXX هەولێر پێنجی
    │              ├── Regex Layer 2: any 100k–200k number on matching line
    │              ├── Validate: 100,000 ≤ price ≤ 200,000
    │              ├── Need exactly 1 penzi + 1 sur
    │              └── Anomaly guard: |new_avg - last_avg| ≤ 10,000
    │
    ├── 3. db.insert_rate(penzi, sur, average, msg_id, created_at)
    │        └── asyncpg INSERT … ON CONFLICT (source_message_id) → unique skip
    │
    ├── 4. refresh_cache() → load latest row into _cached_rate (memory)
    │
    └── 5. ws_manager.broadcast(RateResponse) → push to all WS clients
```

### 4.2 API Request Flow

```
Client HTTP GET /api/rate/latest
    → routes.py handler
    → reads _cached_rate (memory, no DB hit)
    → returns RateResponse JSON

Client HTTP GET /api/rate/history?days=7
    → routes.py handler
    → db.get_rate_history(days=7)   ← SQL: hourly AVG GROUP BY
    → returns list of aggregated rows

Client WS ws://host/ws
    → ws_manager.connect(websocket)
    → client held in active_connections set
    → on new rate: ws_manager.broadcast() pushes JSON to all
```

### 4.3 First-Run Backfill

On startup, if `exchange_rates` table is empty:
1. `fetch_initial_messages(limit=1500)` — fetches last 1500 channel messages.
2. Processes all of them through the same parse → validate → insert pipeline.
3. Refreshes cache after backfill.

---

## 5. Database Schema

**Table: `exchange_rates`** (PostgreSQL)

| Column | Type | Constraint | Description |
|---|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` | Auto-increment row ID |
| `erbil_penzi` | `INTEGER` | `NOT NULL` | Penzi (پێنجی) rate per $100 USD |
| `erbil_sur` | `INTEGER` | `NOT NULL` | Sur (سوور) rate per $100 USD |
| `erbil_average` | `INTEGER` | `NOT NULL` | `round((penzi + sur) / 2)` |
| `source_message_id` | `TEXT` | `NOT NULL UNIQUE` | Telegram message ID (dedup key) |
| `created_at` | `TEXT` | `NOT NULL` | Iraq time ISO 8601 string (UTC+3) |

**Indexes:**
- `PRIMARY KEY` on `id`
- `UNIQUE` on `source_message_id` — prevents duplicate inserts
- `INDEX` on `created_at DESC` — efficient latest-rate and history queries

**Connection:**
- asyncpg connection pool (`min=1, max=10`)
- Pool opened at FastAPI startup, closed at shutdown via lifespan

---

## 6. API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/rate/latest` | Latest rate from memory cache |
| `GET` | `/api/rate/history?days=N` | Aggregated history (hourly for ≤7d, daily for >7d) |
| `GET` | `/api/health` | Status, DB record count |
| `WS` | `/ws` | Real-time rate push stream |

**Conversion endpoints (from original SRS, now handled client-side):**
- The frontend's `converter.js` performs `IQD = USD × (rate / 100)` locally using the cached rate. No server round-trip per conversion.

---

## 7. Configuration

All configuration lives in `app/config.py` as a `settings` singleton.

| Key | Source | Default | Purpose |
|---|---|---|---|
| `TELEGRAM_API_ID` | `.env` | — | Telegram app credential |
| `TELEGRAM_API_HASH` | `.env` | — | Telegram app credential |
| `TELEGRAM_SESSION_STRING` | `.env` | — | Pre-authenticated session (base64) |
| `TELEGRAM_CHANNEL` | `.env` | `@iraqborsa` | Source channel |
| `DATABASE_URL` | `.env` | — | PostgreSQL DSN |
| `FETCH_INTERVAL_SECONDS` | code | `300` | Scheduler interval (5 min) |
| `MIN_VALID_PRICE` | code | `100000` | Lower bound for valid rate |
| `MAX_VALID_PRICE` | code | `200000` | Upper bound for valid rate |
| `MAX_ANOMALY_DEVIATION` | code | `10000` | Max jump from last stored avg |
| `INITIAL_FETCH_COUNT` | code | `1500` | Messages to backfill on first run |

---

## 8. Parser Engine

### Dual Keyword Dialects Supported

| Dialect | Rate Type Keywords | Description |
|---|---|---|
| Wholesale | `پێنجی` (Penzi), `سوور` (Sur) | Standard wholesale market |
| Retail | `کڕین` (Krin/Buy), `فرۆشتن` (Froshtn/Sell) | Retail direction-based |

All require `هەولێر` (Erbil) on the same line.

### Parse Pipeline (per message)

```
1. EXCLUDE CHECK     — gold keywords (ذهب / زێر / الذهب)? → skip
2. SPLIT INTO LINES  — process line by line
3. LINE FILTER       — needs هەولێر + (پێنجی | سوور | کڕین | فرۆشتن)
4. LAYER 1 REGEX     — \$?100\$?\s*=\s*([0-9,]+)\s+هەولێر
5. LAYER 2 REGEX     — any 6-digit number 100000–199999 on matching line
6. VALIDATE          — 100,000 ≤ price ≤ 200,000
7. COMPLETENESS      — need exactly 1 penzi + 1 sur (or krin + froshtn)
8. AVERAGE           — round((penzi + sur) / 2)
9. ANOMALY GUARD     — |new_avg - last_avg| ≤ 10,000
```

---

## 9. Error Handling Strategy

| Scenario | Behavior |
|---|---|
| Telegram unreachable | Log, skip cycle, serve last valid cached rate |
| Message parse fails | Log raw text + reason, skip message |
| Anomaly detected | Log with context, skip — do not store |
| Duplicate message ID | DB UNIQUE constraint silently skips |
| DB write failure | Log error, retry next cycle |
| No stored data yet | API returns `503 Service Unavailable` |
| Session expired | Log critical, requires re-running `extract_session.py` |
| WS client disconnects | `ws_manager` removes from set, no crash |

---

## 10. Deployment

- **Platform:** Render.com (Web Service)
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port 10000`
- **Build command:** `pip install -r requirements.txt`
- **Environment:** All `.env` variables injected via Render dashboard
- **Database:** Render-managed PostgreSQL (or external DSN via `DATABASE_URL`)
- **Session:** `TELEGRAM_SESSION_STRING` stored as Render secret env var (generated once via `extract_session.py`)
