# Changelog

All notable changes to ErbilRate API are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.2.0] — 2026-04-28

### Security
- RS256 JWT signature verification using Clerk JWKS endpoint (replaced insecure decode-only)
- JWKS cached in Redis (1-hour TTL) with automatic key-rotation detection
- Brute-force IP blocking: 10 failed auth attempts triggers 15-minute IP ban
- CORS locked to `ALLOWED_ORIGINS` env var — wildcard `*` removed
- Request ID middleware: every response carries `X-Request-ID` for tracing
- Oversized API key rejection (>256 chars) to prevent CPU-exhaustion attacks
- Email removed from `/api/me` response to prevent account detail leakage

### Added
- `GET /api/health` — public slim endpoint (status only, no internal metrics)
- `GET /api/health/detailed` — full metrics, requires API key
- WebSocket per-IP connection limiting (max 5 concurrent per IP)
- WebSocket optional API key validation via `?api_key=` query param
- Telegram sender ID allowlist — only trusted sender IDs reach the parser
- Pub/Sub reconnect alerting: escalates to ERROR after 3 reconnects in 10 min
- `scripts/security_test_suite.py` — 47-test automated security audit

### Changed
- Conversion endpoints now require API key (previously open)
- Conversion endpoints now read from Redis cache first (DB fallback)
- `GET /api/me` no longer returns email address

### Fixed
- Division-by-zero guard on conversion endpoints when average = 0
- DB CHECK constraints: `erbil_average > 0`, `erbil_penzi > 0`, `erbil_sur > 0`

---

## [1.1.0] — 2026-04-15

### Added
- WebSocket real-time rate feed (`/api/ws`)
- Redis Pub/Sub broadcasting to all connected WebSocket clients
- Exponential backoff reconnect loop for Pub/Sub connection drops
- Admin dashboard routes (`/api/admin/*`) protected by Clerk JWT
- API key generation, listing, and revocation for developers
- Token budget system: 10,000 tokens/day on free tier
- Speed limit: 300 requests/minute per API key

### Changed
- Migrated from SQLite to PostgreSQL (asyncpg connection pool)
- Redis added as caching and rate-limiting layer (Upstash)

---

## [1.0.0] — 2026-03-01

### Added
- Initial release
- Real-time Telegram event listener for `@iraqborsa`
- 5-minute polling safety net
- Kurdish/Arabic dual-dialect rate parser
- Bronze layer: `raw_messages` table
- Gold layer: `exchange_rates` table
- `GET /api/rate/latest` — latest Erbil rate
- `GET /api/rate/history` — 1d / 7d / 30d / 90d historical data
- `GET /api/convert/usd-to-iqd` and `GET /api/convert/iqd-to-usd`
- Redis caching for latest rate and history pre-computation
- PWA frontend with bilingual support (English / Kurdish)
- SVG-based historical charts (no external charting library)
- Dark/light mode, offline support
