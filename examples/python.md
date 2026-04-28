# Python Integration

## Install
```bash
pip install httpx  # or use requests
```

---

## Get the Latest Rate

```python
import httpx

API_KEY  = "YOUR_API_KEY"
BASE_URL = "https://usd-ih41.onrender.com/api"

def get_latest_rate() -> dict:
    with httpx.Client(headers={"X-API-Key": API_KEY}) as client:
        response = client.get(f"{BASE_URL}/rate/latest")
        response.raise_for_status()
        data = response.json()
    print(f"1 USD = {data['average']:,} IQD (Erbil mid-market)")
    print(f"Updated: {data['last_updated']}")
    return data

if __name__ == "__main__":
    rate = get_latest_rate()
```

---

## Convert USD → IQD

```python
def usd_to_iqd(amount: float) -> dict:
    with httpx.Client(headers={"X-API-Key": API_KEY}) as client:
        response = client.get(
            f"{BASE_URL}/convert/usd-to-iqd",
            params={"amount": amount}
        )
        response.raise_for_status()
        result = response.json()
    print(f"{result['usd']} USD = {result['iqd']:,} IQD")
    return result

usd_to_iqd(500)
```

---

## Historical Rates

```python
def get_history(days: int = 7) -> list[dict]:
    """Returns daily aggregated rates. days: 1, 7, 30, or 90."""
    with httpx.Client(headers={"X-API-Key": API_KEY}) as client:
        response = client.get(
            f"{BASE_URL}/rate/history",
            params={"days": days}
        )
        response.raise_for_status()
        return response.json()["rates"]

for record in get_history(30):
    print(f"{record['date']}: {record['average']:,} IQD")
```

---

## Async Version (for FastAPI / async frameworks)

```python
import httpx
import asyncio

async def get_latest_rate_async() -> dict:
    async with httpx.AsyncClient(headers={"X-API-Key": API_KEY}) as client:
        response = await client.get(f"{BASE_URL}/rate/latest")
        response.raise_for_status()
        return response.json()

asyncio.run(get_latest_rate_async())
```

---

## WebSocket — Live Rate Stream

```python
import asyncio
import json
import websockets

async def live_feed():
    uri = "wss://usd-ih41.onrender.com/api/ws"

    async for websocket in websockets.connect(uri):
        try:
            print("Connected to ErbilRate live feed")
            async for message in websocket:
                if message == "pong":
                    continue
                rate = json.loads(message)
                if "average" in rate:
                    print(f"LIVE: 1 USD = {rate['average']:,} IQD")
        except websockets.ConnectionClosed:
            print("Disconnected — reconnecting...")
            await asyncio.sleep(5)

asyncio.run(live_feed())
```

---

## Error Handling

```python
import httpx

def safe_get_rate() -> dict | None:
    try:
        with httpx.Client(headers={"X-API-Key": API_KEY}, timeout=10.0) as client:
            response = client.get(f"{BASE_URL}/rate/latest")

            if response.status_code == 401:
                print("Invalid API key. Check your key at erbilrate.com.")
                return None

            if response.status_code == 429:
                print("Rate limit exceeded. Slow down your requests.")
                return None

            response.raise_for_status()
            return response.json()

    except httpx.TimeoutException:
        print("Request timed out. Retry later.")
        return None
    except httpx.HTTPError as e:
        print(f"HTTP error: {e}")
        return None
```
