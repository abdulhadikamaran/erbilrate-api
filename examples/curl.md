# cURL Integration

Quick reference for testing and scripting. Replace `YOUR_API_KEY` in every command.

---

## Get the Latest Rate

```bash
curl https://usd-ih41.onrender.com/api/rate/latest \
  -H "X-API-Key: YOUR_API_KEY"
```

**Response:**
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

---

## Convert USD to IQD

```bash
curl "https://usd-ih41.onrender.com/api/convert/usd-to-iqd?amount=250" \
  -H "X-API-Key: YOUR_API_KEY"
```

---

## Convert IQD to USD

```bash
curl "https://usd-ih41.onrender.com/api/convert/iqd-to-usd?amount=500000" \
  -H "X-API-Key: YOUR_API_KEY"
```

---

## Get Historical Rates (7 days)

```bash
curl "https://usd-ih41.onrender.com/api/rate/history?days=7" \
  -H "X-API-Key: YOUR_API_KEY"
```

---

## Check Your API Key Usage

```bash
curl https://usd-ih41.onrender.com/api/me \
  -H "X-API-Key: YOUR_API_KEY"
```

**Response:**
```json
{
  "tier": "free",
  "usage": 42,
  "remaining": 9958,
  "daily_limit": 10000
}
```

---

## Check API Health (no key required)

```bash
curl https://usd-ih41.onrender.com/api/health
```

---

## Use the Request ID for Debugging

Every response includes an `X-Request-ID` header. Pass your own to trace requests:

```bash
curl https://usd-ih41.onrender.com/api/rate/latest \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "X-Request-ID: my-debug-id-001" \
  -i
```

The same ID will appear in the response headers — useful for support requests.

---

## Pretty Print with jq

```bash
curl -s https://usd-ih41.onrender.com/api/rate/latest \
  -H "X-API-Key: YOUR_API_KEY" | jq .
```

---

## Automation Script Example (bash)

```bash
#!/bin/bash
# poll-rate.sh — Prints the current rate every 60 seconds

API_KEY="YOUR_API_KEY"

while true; do
  RATE=$(curl -s "https://usd-ih41.onrender.com/api/rate/latest" \
    -H "X-API-Key: $API_KEY" | jq -r '.average')
  echo "$(date '+%H:%M:%S') — 1 USD = $RATE IQD"
  sleep 60
done
```
