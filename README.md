<div align="center">

<img src="static/icons/icon-192.png" alt="ErbilRate Logo" width="80"/>

# ErbilRate API

### Real-time Iraqi Dinar Exchange Rates — Built for Developers

**The fastest, most reliable USD/IQD exchange rate API for Erbil, Iraq.**  
Live market data. Instant WebSocket feed. Free tier. No credit card required.

[![API Status](https://img.shields.io/badge/API%20Status-Operational-brightgreen?style=flat-square)](https://usd-ih41.onrender.com/api/health)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![Security](https://img.shields.io/badge/Security-RS256%20JWT-orange?style=flat-square)](docs/authentication.md)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-erbilrate.com-success?style=flat-square)](https://usd-ih41.onrender.com/)

[Get API Key](https://usd-ih41.onrender.com/) · [Documentation](https://usd-ih41.onrender.com/docs) · [Live Demo](https://usd-ih41.onrender.com/)

</div>

---

## What is ErbilRate?

ErbilRate is a **financial data API** that provides real-time USD/IQD exchange rates sourced directly from the Erbil, Iraq currency market — updated the instant the market moves, not once a day.

Most global FX APIs (Fixer, OpenExchangeRates, XE) either don't carry IQD at all, or they publish a single government rate that doesn't reflect what the Erbil bazaar is actually trading at. ErbilRate fixes that.

**Who uses it:**
- 💰 Fintech apps and digital wallets handling IQD
- 🏪 E-commerce sites displaying prices in both USD and IQD
- 📱 Flutter / React Native apps with a currency converter
- 🤖 Trading bots and financial dashboards
- 📊 Business intelligence tools tracking exchange trends

---

## 60-Second Quick Start

**Step 1 — Get your free API key**  
Go to [erbilrate.com](https://usd-ih41.onrender.com/) → Sign in → Generate Key. Takes 30 seconds.

**Step 2 — Make your first request**

```bash
curl https://usd-ih41.onrender.com/api/rate/latest \
  -H "X-API-Key: YOUR_API_KEY"
```

**Step 3 — See live market data**

```json
{
  "average": 149800,
  "penzi": 149700,
  "sur": 149900,
  "daily_change": -50,
  "last_updated": "2026-04-28T17:34:00Z",
  "city": "Erbil"
}
```

That's it. You're live. `average` is the mid-market rate per 100 USD in IQD.

---

## API Reference

### Base URL
```
https://usd-ih41.onrender.com/api
```

### Authentication
All endpoints accept your API key via the `X-API-Key` header:
```
X-API-Key: er_live_xxxxxxxxxxxxxxxxxxxx
```

### Endpoints

| Endpoint | Method | Description | Auth | Token Cost |
|---|---|---|---|---|
| `/rate/latest` | GET | Latest Erbil USD/IQD rate | Required | 1 |
| `/rate/history` | GET | Historical rates (1d / 7d / 30d / 90d) | Required | = days |
| `/convert/usd-to-iqd` | GET | Convert USD amount → IQD | Required | 1 |
| `/convert/iqd-to-usd` | GET | Convert IQD amount → USD | Required | 1 |
| `/health` | GET | API status | None | Free |
| `/ws` | WebSocket | Real-time rate stream | Optional | Free |

---

### `GET /rate/latest`
Returns the current Erbil market rate.

**Response**
```json
{
  "average": 149800,
  "penzi": 149700,
  "sur":    149900,
  "daily_change": -50,
  "last_updated": "2026-04-28T17:34:00Z",
  "city": "Erbil"
}
```

| Field | Type | Description |
|---|---|---|
| `average` | integer | Mid-market rate (IQD per 100 USD) |
| `penzi` | integer | Wholesale buy rate |
| `sur` | integer | Wholesale sell rate |
| `daily_change` | integer | Change vs. yesterday's average |
| `last_updated` | ISO 8601 | Timestamp of last market update |

---

### `GET /rate/history?days=7`
Returns aggregated daily rates for charting.

**Parameters**

| Name | Type | Required | Values |
|---|---|---|---|
| `days` | integer | Yes | `1`, `7`, `30`, `90` |

**Response**
```json
{
  "city": "Erbil",
  "count": 7,
  "rates": [
    { "date": "2026-04-22", "average": 149750, "penzi": 149650, "sur": 149850 },
    { "date": "2026-04-23", "average": 149800, "penzi": 149700, "sur": 149900 }
  ]
}
```

---

### `GET /convert/usd-to-iqd?amount=100`
Converts a USD amount to IQD at the current Erbil rate.

```json
{ "usd": 100, "iqd": 149800, "rate_per_100": 149800 }
```

---

### `GET /convert/iqd-to-usd?amount=149800`
Converts an IQD amount to USD at the current Erbil rate.

```json
{ "iqd": 149800, "usd": 100.0, "rate_per_100": 149800 }
```

---

### WebSocket — Real-Time Feed
Connect to receive instant rate updates the moment the market moves.

```
wss://usd-ih41.onrender.com/api/ws
```

With an API key (developer mode):
```
wss://usd-ih41.onrender.com/api/ws?api_key=YOUR_API_KEY
```

**Incoming message format:**
```json
{
  "average": 149800,
  "penzi": 149700,
  "sur": 149900,
  "daily_change": -50,
  "last_updated": "2026-04-28T17:34:00Z"
}
```

Send `ping` to keep the connection alive. The server responds with `pong`.

---

## Integration Examples

Ready-to-use code snippets for your language:

- [JavaScript / Node.js](examples/javascript.md)
- [Python](examples/python.md)
- [PHP](examples/php.md)
- [Dart / Flutter](examples/flutter.md)
- [cURL](examples/curl.md)

---

## Rate Limits

ErbilRate uses a **token budget system**. Each API call costs tokens from your daily budget.

| Tier | Daily Token Budget | Speed Limit | Price |
|---|---|---|---|
| **Free** | 10,000 tokens/day | 300 req/min | Free forever |
| **Pro** | 500,000 tokens/day | 1,000 req/min | Coming soon |

**Token costs per endpoint:**

| Endpoint | Cost |
|---|---|
| `/rate/latest` | 1 token |
| `/convert/*` | 1 token each |
| `/rate/history?days=7` | 7 tokens |
| `/health` | Free |
| WebSocket feed | Free (connection-based) |

Check your current usage anytime:
```bash
curl https://usd-ih41.onrender.com/api/me \
  -H "X-API-Key: YOUR_API_KEY"
```

---

## Error Reference

All errors return a consistent JSON body:

```json
{ "detail": "Human-readable description of the error." }
```

| HTTP Code | Meaning | What to do |
|---|---|---|
| `400` | Bad request (invalid parameter format) | Check your query parameters |
| `401` | Invalid or revoked API key | Check your key, regenerate if needed |
| `422` | Validation error (value out of range) | Read the detail field |
| `429` | Rate limit exceeded | Wait and retry with backoff |
| `503` | No rate data available yet | Rare — retry in 60 seconds |

Every response includes an `X-Request-ID` header. Include this in support requests.

---

## Security

ErbilRate is built with production-grade security:

- **RS256 JWT verification** — All admin tokens verified against Clerk's JWKS endpoint
- **Brute-force protection** — IPs blocked after 10 failed auth attempts (15-minute window)
- **CORS lockdown** — Restricted to known origins (no wildcard `*`)
- **Input validation** — All parameters strictly schema-validated before any DB call
- **DB constraints** — Database-level `CHECK` constraints prevent invalid rate data
- **Request tracing** — Every request carries a unique `X-Request-ID` for incident response

Full security test suite: [`scripts/security_test_suite.py`](scripts/security_test_suite.py)  
Last audit: **2026-04-28 — 47/47 tests passed (100%)**

---

## Self-Hosting

This repository contains the complete API layer — authentication, rate limiting, WebSocket infrastructure, database schema, and frontend. You can run it against your own data source.

**Requirements:**
- Python 3.11+
- PostgreSQL 14+
- Redis (Upstash or self-hosted)
- A Clerk account (for admin JWT auth)

```bash
git clone https://github.com/YOUR_USERNAME/erbilrate-api
cd erbilrate-api
pip install -r requirements.txt
cp .env.example .env
# Fill in your own .env values
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

See [`.env.example`](.env.example) for all required configuration.

> **Note:** The live ErbilRate service uses a proprietary real-time data pipeline not included in this repository. This repo gives you the full API infrastructure — bring your own data source.

---

## Contributing

Contributions are welcome! Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request.

Areas where help is most appreciated:
- SDK clients (Go, Swift, Kotlin)
- Translation improvements for Kurdish/Arabic error messages
- Additional test coverage

---

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md) for the full version history.

**Latest — v1.2.0 (2026-04-28)**
- RS256 JWT verification with JWKS caching
- Brute-force IP blocking (10 attempts / 15-min window)
- Request ID tracing on every response
- DB-level CHECK constraints on all rate fields
- CORS locked to production domains
- Public `/health` + authenticated `/health/detailed` split

---

## License

MIT © ErbilRate — see [`LICENSE`](LICENSE) for details.

---

<div align="center">
  <sub>Built in Erbil, Iraq 🇮🇶 — For developers who need real market data, not government approximations.</sub>
</div>
