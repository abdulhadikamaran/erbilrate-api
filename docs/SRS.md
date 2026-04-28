# Software Requirements Specification (SRS)
## Erbil USD/IQD Market Rate Platform

| Field | Value |
|---|---|
| **Version** | 3.0 — As-Built |
| **Date** | 2026-04-27 |
| **Status** | ✅ Implemented & Deployed |

> **Note:** This document reflects the system **as it is actually built and running**, not an original planning spec. It is the authoritative reference for what the system does.

---

## 1. System Overview

An automated, real-time pipeline that:
1. Reads public USD/IQD rate messages from a Telegram channel (`@iraqborsa`).
2. Parses the Kurdish/Arabic formatted messages to extract Erbil market rates.
3. Stores validated rates in PostgreSQL.
4. Exposes a REST API + WebSocket stream.
5. Serves a bilingual (Kurdish/English) Progressive Web App as the frontend.

### High-Level Data Flow

```
@iraqborsa (Telegram)
    │  Telethon Client API (polled every 5 min)
    ▼
Parser Engine
    │  Filter → Extract → Validate → Anomaly Check
    ▼
PostgreSQL (exchange_rates table)
    │
    ├──► REST API  (GET /api/rate/latest, /history, /health)
    └──► WebSocket (/ws) → push to all connected clients
                               │
                               ▼
                    PWA Frontend (static/index.html)
```

---

## 2. Functional Requirements

### FR-1: Telegram Ingestion

| ID | Requirement | Status |
|---|---|---|
| FR-1.1 | Connect to `@iraqborsa` via Telethon using a pre-authenticated session string | ✅ |
| FR-1.2 | Poll for new messages every 5 minutes via asyncio scheduler loop | ✅ |
| FR-1.3 | Track last processed `source_message_id` to avoid re-processing | ✅ |
| FR-1.4 | On first run (empty DB): backfill last 1500 messages | ✅ |

### FR-2: Message Parsing

| ID | Requirement | Status |
|---|---|---|
| FR-2.1 | Skip entire messages containing gold keywords: `ذهب`, `زێر`, `الذهب` | ✅ |
| FR-2.2 | Process messages line by line | ✅ |
| FR-2.3 | A valid line must contain `هەولێر` AND one of: `پێنجی`, `سوور`, `کڕین`, `فرۆشتن` | ✅ |
| FR-2.4 | Layer 1 regex: matches `$100=XXX,XXX هەولێر پێنجی` format | ✅ |
| FR-2.5 | Layer 2 regex: fallback — any 6-digit number on a qualifying line | ✅ |
| FR-2.6 | Validate extracted price: 100,000 ≤ price ≤ 200,000 | ✅ |
| FR-2.7 | A valid parse requires exactly 1 penzi + 1 sur value | ✅ |
| FR-2.8 | Anomaly guard: reject if `|new_avg − last_avg| > 10,000` | ✅ |

### FR-3: Storage

| ID | Requirement | Status |
|---|---|---|
| FR-3.1 | Store validated rates in PostgreSQL table `exchange_rates` | ✅ |
| FR-3.2 | Append-only — records are never updated or deleted | ✅ |
| FR-3.3 | `source_message_id` has a UNIQUE constraint to prevent duplicates | ✅ |
| FR-3.4 | Timestamps stored as Iraq time (UTC+3) ISO 8601 string | ✅ |

### FR-4: REST API

| Endpoint | Description | Status |
|---|---|---|
| `GET /api/rate/latest` | Latest rate (served from memory cache, no DB hit) | ✅ |
| `GET /api/rate/history?days=N` | Aggregated history; hourly AVG for ≤7d, daily AVG for >7d | ✅ |
| `GET /api/health` | System status + DB record count | ✅ |

### FR-5: WebSocket

| ID | Requirement | Status |
|---|---|---|
| FR-5.1 | `WS /ws` — clients connect and receive rate push notifications | ✅ |
| FR-5.2 | On each new valid rate stored, broadcast to all connected clients | ✅ |
| FR-5.3 | Disconnected clients are cleanly removed from the active set | ✅ |

### FR-6: Frontend PWA

| ID | Requirement | Status |
|---|---|---|
| FR-6.1 | Single-page app served at `GET /` from `static/index.html` | ✅ |
| FR-6.2 | Display live rate card with average, penzi, sur, direction arrow, timestamp | ✅ |
| FR-6.3 | Real-time updates via WebSocket (no page reload) | ✅ |
| FR-6.4 | Currency converter (USD ↔ IQD) using cached rate — works offline | ✅ |
| FR-6.5 | Today's hourly chart + 7D/30D/90D history charts (Chart.js) | ✅ |
| FR-6.6 | Bilingual: Kurdish (RTL) / English (LTR) toggle with localStorage persistence | ✅ |
| FR-6.7 | Auto dark/light theme via `prefers-color-scheme` | ✅ |
| FR-6.8 | PWA: installable, offline-capable via Service Worker + localStorage cache | ✅ |

---

## 3. Non-Functional Requirements

### NFR-1: Performance

| ID | Requirement |
|---|---|
| NFR-1.1 | API response latency < 300ms (p95) |
| NFR-1.2 | `/api/rate/latest` served from memory cache — no DB query |
| NFR-1.3 | Frontend initial render < 1 second on repeat visit (cached assets) |

### NFR-2: Reliability

| ID | Requirement |
|---|---|
| NFR-2.1 | Scheduler errors must not crash the API server |
| NFR-2.2 | When Telegram is unreachable, API continues serving last valid rate |
| NFR-2.3 | Parser resilient to minor format variations via dual-layer regex |

### NFR-3: Security

| ID | Requirement |
|---|---|
| NFR-3.1 | Telegram credentials and DB URL stored in `.env`, gitignored |
| NFR-3.2 | Session files (`*.session`) gitignored |
| NFR-3.3 | Session string stored as environment secret in deployment platform |

### NFR-4: Maintainability

| ID | Requirement |
|---|---|
| NFR-4.1 | All parser keywords and thresholds configurable in `app/config.py` |
| NFR-4.2 | No SQL outside `app/database.py` |
| NFR-4.3 | WebSocket management fully isolated in `app/ws_manager.py` |

---

## 4. Data Model

**Table: `exchange_rates`** (PostgreSQL)

| Column | Type | Constraint | Description |
|---|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` | Row identifier |
| `erbil_penzi` | `INTEGER` | `NOT NULL` | Penzi rate per $100 USD |
| `erbil_sur` | `INTEGER` | `NOT NULL` | Sur rate per $100 USD |
| `erbil_average` | `INTEGER` | `NOT NULL` | `round((penzi + sur) / 2)` |
| `source_message_id` | `TEXT` | `NOT NULL UNIQUE` | Telegram message ID |
| `created_at` | `TEXT` | `NOT NULL` | Iraq time ISO 8601 (UTC+3) |

---

## 5. Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| Web Framework | FastAPI |
| ASGI Server | Uvicorn |
| Telegram Client | Telethon (session string auth) |
| Database | PostgreSQL via asyncpg |
| Real-Time | WebSockets (FastAPI native) |
| Frontend | Vanilla JS (ES Modules) + Tailwind CSS v3 |
| Charts | Chart.js (CDN) |
| PWA | Service Worker + Web App Manifest |
| Config | python-dotenv |
| Hosting | Render.com |

---

## 6. Glossary

| Term | Definition |
|---|---|
| **Penzi (پێنجی)** | Erbil wholesale market rate type |
| **Sur (سوور)** | Erbil wholesale market rate type (lit. "red") |
| **Krin (کڕین)** | Retail buy rate |
| **Froshtn (فرۆشتن)** | Retail sell rate |
| **IQD** | Iraqi Dinar |
| **Anomaly Guard** | Rejects rates deviating > 10,000 IQD from last stored average |
| **Session String** | Base64-encoded Telethon auth token — eliminates interactive OTP on server |
| **Backfill** | First-run process that hydrates an empty DB from channel history |
| **@iraqborsa** | The Telegram channel that is the sole data source |
