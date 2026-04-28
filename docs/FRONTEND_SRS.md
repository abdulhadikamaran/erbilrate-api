# Frontend Reference
## نرخی دۆلار — Erbil USD/IQD Rate PWA

| Field | Value |
|---|---|
| **Status** | ✅ Implemented & Deployed |
| **Last Updated** | 2026-04-27 |
| **Live URL** | https://usd-ih41.onrender.com/ |

---

## 1. Overview

A mobile-first Progressive Web App serving as the user-facing frontend.
Served directly by FastAPI at `GET /` from `static/index.html`.

**Core value:** Open the app → see the dollar rate in under 1 second. Convert currencies instantly. Works offline. No login.

---

## 2. File Structure

```
static/
├── index.html              # Single-page PWA shell
├── js/
│   ├── app.js              # Main controller: init, WS listener, rate display, charts init
│   ├── converter.js        # Real-time USD ↔ IQD converter
│   ├── chart.js            # Chart.js rendering (today hourly + 7D/30D/90D history)
│   ├── cache.js            # localStorage cache manager
│   ├── i18n.js             # Kurdish / English translation system
│   └── tailwindcss.js      # Tailwind CSS runtime (bundled locally)
├── icons/                  # PWA icons (192px, 512px)
└── flags/                  # Flag images used in UI
```

---

## 3. Tech Stack

| Component | Technology |
|---|---|
| Structure | HTML5 — single `index.html` |
| Styling | Tailwind CSS v3 (local bundle, no CDN dependency) |
| Logic | Vanilla JavaScript — ES Modules, no framework |
| Charts | Chart.js (CDN) |
| PWA | Service Worker + Web App Manifest |
| Data Cache | localStorage |
| Hosting | Served by FastAPI `StaticFiles` middleware |
| Fonts | Google Fonts — Inter |

---

## 4. Features

### 4.1 Live Rate Display (Hero)
- Large, bold average rate number
- Direction indicator: ▲ green (up) / ▼ red (down) vs previous rate
- Relative timestamp ("5 mins ago"), updated every minute via `setInterval`
- Rates update live via WebSocket — no page reload required

### 4.2 Currency Converter
- USD ↔ IQD, two input fields
- Real-time calculation on every keystroke (`input` event) — **no API call per conversion**
- Formula: `IQD = USD × (average / 100)` and reverse
- Swap button with 180° rotation animation
- Uses locally cached rate — fully works offline

### 4.3 Today's Hourly Chart
- Line chart from `GET /api/rate/history?days=1`
- X-axis adapts to actual data hours (not hardcoded)
- Shows "No data yet today" when empty

### 4.4 History Dashboard
- Tabs: **7D** | **30D** | **90D**
- Data from `GET /api/rate/history?days=N`
- Daily average line chart for each period
- 7D view: tap a day → expands hourly drill-down chart below

### 4.5 Bilingual Support
- **Kurdish (Sorani)** — RTL, Arabic script (default)
- **English** — LTR
- Toggle button switches all text and layout direction instantly (no reload)
- Preference saved in `localStorage`

### 4.6 Auto Dark / Light Theme
- CSS `prefers-color-scheme` media query — follows system setting
- No manual toggle

### 4.7 Offline / PWA
- Service Worker: caches HTML, CSS, JS, fonts on first visit
- localStorage: caches latest rate + history data
- Converter works 100% offline (just math on cached rate)
- Stale cache (>1 hour old + offline): shows amber warning banner
- Installable on iOS/Android ("Add to Home Screen")

---

## 5. Data Flow

```
App opens
    │
    ├── 1. Show cached rate from localStorage instantly (<100ms)
    │
    ├── 2. If cache > 1 hour old AND online → fetch /api/rate/latest
    │         └── Update display + save new cache
    │
    ├── 3. If cache > 1 hour old AND offline → amber warning banner
    │
    ├── 4. Open WebSocket to /ws
    │         └── On push event → update rate display + re-calculate converter
    │
    └── 5. On chart tab open → fetch /api/rate/history?days=N if cache stale
```

---

## 6. Color Palette

**Dark Theme (default for dark system preference):**

| Element | Color |
|---|---|
| Background | `#0f1923` |
| Card background | `rgba(255,255,255,0.05)` + `backdrop-filter: blur` |
| Primary text | `#f0f0f0` |
| Accent / chart | Gold `#f0b429` |
| Up indicator | `#10b981` |
| Down indicator | `#ef4444` |

**Light Theme:**

| Element | Color |
|---|---|
| Background | `#f8f9fa` |
| Card background | `#ffffff` |
| Primary text | `#1a202c` |
| Accent / chart | `#2563eb` |
| Up indicator | `#059669` |
| Down indicator | `#dc2626` |

---

## 7. Translations Reference

| Key | Kurdish (ku) | English (en) |
|---|---|---|
| `app_name` | نرخی دۆلار | Dollar Rate |
| `rate_label` | نرخی بازاڕی هەولێر | Erbil Market Rate |
| `per_100` | IQD بۆ $100 | IQD per $100 |
| `updated_ago` | {n} خولەک لەمەوپێش | {n} mins ago |
| `converter` | گۆڕینی دراو | Currency Converter |
| `today` | ئەمڕۆ | Today |
| `days_7` | ٧ ڕۆژ | 7 Days |
| `days_30` | ٣٠ ڕۆژ | 30 Days |
| `days_90` | ٩٠ ڕۆژ | 90 Days |
| `offline_banner` | ئۆفلاین — نرخی {time} لەمەوپێش | Offline — rate from {time} ago |
| `market_closed` | بازاڕ داخراوە | Market Closed |
| `no_data` | هیچ داتایەک نییە | No data available |

---

## 8. PWA Manifest Summary

```json
{
  "name": "نرخی دۆلار — Erbil Dollar Rate",
  "short_name": "نرخی دۆلار",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0f1923",
  "theme_color": "#f0b429",
  "lang": "ku",
  "dir": "rtl"
}
```

---

## 9. Error States

| Scenario | Display |
|---|---|
| First visit, no internet | "Connect to internet to get started" + retry button |
| API error (server down) | Use cached data + amber banner: "Server unreachable" |
| No data in DB yet | "Data not available yet — check back soon" |
| History has no data | "No records for this period" with empty chart placeholder |
