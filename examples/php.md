# PHP Integration

## Requirements
PHP 7.4+ with `curl` extension (enabled by default on most hosts).

---

## Get the Latest Rate

```php
<?php

define('ERBILRATE_API_KEY', 'YOUR_API_KEY');
define('ERBILRATE_BASE_URL', 'https://usd-ih41.onrender.com/api');

function erbilrate_get(string $endpoint, array $params = []): array
{
    $url = ERBILRATE_BASE_URL . $endpoint;
    if (!empty($params)) {
        $url .= '?' . http_build_query($params);
    }

    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 10,
        CURLOPT_HTTPHEADER     => [
            'X-API-Key: ' . ERBILRATE_API_KEY,
            'Accept: application/json',
        ],
    ]);

    $body    = curl_exec($ch);
    $status  = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error   = curl_error($ch);
    curl_close($ch);

    if ($error) {
        throw new RuntimeException("cURL error: $error");
    }

    $data = json_decode($body, true);

    if ($status === 401) {
        throw new RuntimeException("Invalid API key.");
    }
    if ($status === 429) {
        throw new RuntimeException("Rate limit exceeded. Try again later.");
    }
    if ($status >= 400) {
        throw new RuntimeException("API error $status: " . ($data['detail'] ?? 'Unknown'));
    }

    return $data;
}

// Usage
$rate = erbilrate_get('/rate/latest');
echo "1 USD = " . number_format($rate['average']) . " IQD\n";
echo "Updated: " . $rate['last_updated'] . "\n";
```

---

## Convert USD to IQD

```php
$result = erbilrate_get('/convert/usd-to-iqd', ['amount' => 500]);
echo $result['usd'] . " USD = " . number_format($result['iqd']) . " IQD\n";
```

---

## Get Historical Rates

```php
$history = erbilrate_get('/rate/history', ['days' => 7]);

foreach ($history['rates'] as $record) {
    echo $record['date'] . ": " . number_format($record['average']) . " IQD\n";
}
```

---

## WordPress / WooCommerce Example

Display the live rate in a WordPress shortcode:

```php
// Add to your theme's functions.php

function erbilrate_shortcode(): string
{
    try {
        $rate = erbilrate_get('/rate/latest');
        $avg  = number_format($rate['average']);
        return "<span class='erbilrate'>1 USD = {$avg} IQD</span>";
    } catch (Exception $e) {
        return "<span class='erbilrate-error'>Rate unavailable</span>";
    }
}

add_shortcode('erbilrate', 'erbilrate_shortcode');
// Use in posts/pages: [erbilrate]
```

---

## Cache Responses (Simple File Cache)

ErbilRate updates in real-time, but for high-traffic sites you may want to cache locally:

```php
function erbilrate_cached(int $ttl_seconds = 60): array
{
    $cache_file = sys_get_temp_dir() . '/erbilrate_latest.json';

    if (file_exists($cache_file) && (time() - filemtime($cache_file)) < $ttl_seconds) {
        return json_decode(file_get_contents($cache_file), true);
    }

    $data = erbilrate_get('/rate/latest');
    file_put_contents($cache_file, json_encode($data));
    return $data;
}

$rate = erbilrate_cached(60); // fresh every 60 seconds
echo number_format($rate['average']) . " IQD per USD\n";
```
