# JavaScript / Node.js Integration

## Install
No dependencies required. Uses the native `fetch` API (Node 18+ / all browsers).

---

## Get the Latest Rate

```javascript
const API_KEY = 'YOUR_API_KEY';
const BASE_URL = 'https://usd-ih41.onrender.com/api';

async function getLatestRate() {
  const response = await fetch(`${BASE_URL}/rate/latest`, {
    headers: { 'X-API-Key': API_KEY },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(`API error ${response.status}: ${error.detail}`);
  }

  const data = await response.json();
  console.log(`1 USD = ${data.average} IQD (Erbil mid-market)`);
  console.log(`Updated: ${data.last_updated}`);
  return data;
}

getLatestRate().catch(console.error);
```

---

## Convert USD to IQD

```javascript
async function convertUsdToIqd(usdAmount) {
  const response = await fetch(
    `${BASE_URL}/convert/usd-to-iqd?amount=${usdAmount}`,
    { headers: { 'X-API-Key': API_KEY } }
  );

  if (!response.ok) {
    const err = await response.json();
    throw new Error(`${response.status}: ${err.detail}`);
  }

  const { usd, iqd } = await response.json();
  console.log(`${usd} USD = ${iqd.toLocaleString()} IQD`);
  return iqd;
}
```

---

## Historical Rates (for charting)

```javascript
async function getHistory(days = 7) {
  const response = await fetch(
    `${BASE_URL}/rate/history?days=${days}`,
    { headers: { 'X-API-Key': API_KEY } }
  );

  const { rates } = await response.json();
  // rates = [{ date, average, penzi, sur }, ...]
  rates.forEach(r => console.log(`${r.date}: ${r.average} IQD`));
  return rates;
}
```

---

## WebSocket — Live Rate Updates

```javascript
function connectLiveFeed(onRate) {
  const ws = new WebSocket('wss://usd-ih41.onrender.com/api/ws');

  ws.onopen = () => {
    console.log('Connected to ErbilRate live feed');
  };

  ws.onmessage = (event) => {
    const rate = JSON.parse(event.data);
    if (rate.average) onRate(rate);      // rate update
    if (rate === 'pong') return;         // heartbeat response
  };

  ws.onerror = (err) => console.error('WebSocket error:', err);

  ws.onclose = () => {
    console.log('Disconnected — reconnecting in 5s...');
    setTimeout(() => connectLiveFeed(onRate), 5000);
  };

  // Keep-alive ping every 25 seconds
  const ping = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) ws.send('ping');
  }, 25000);

  ws.onclose = () => {
    clearInterval(ping);
    setTimeout(() => connectLiveFeed(onRate), 5000);
  };

  return ws;
}

// Usage
connectLiveFeed((rate) => {
  document.getElementById('rate').textContent =
    `1 USD = ${rate.average.toLocaleString()} IQD`;
});
```

---

## Handle Rate Limits (429)

```javascript
async function fetchWithRetry(url, options, maxRetries = 3) {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const response = await fetch(url, options);

    if (response.status === 429) {
      const waitMs = Math.pow(2, attempt) * 1000; // 1s, 2s, 4s
      console.warn(`Rate limited. Retrying in ${waitMs}ms...`);
      await new Promise(resolve => setTimeout(resolve, waitMs));
      continue;
    }

    return response;
  }
  throw new Error('Max retries exceeded');
}
```
