# Dart / Flutter Integration

## Add Dependency

```yaml
# pubspec.yaml
dependencies:
  http: ^1.2.0
  web_socket_channel: ^3.0.0
```

---

## Service Class

```dart
// lib/services/iqdrate_service.dart

import 'dart:convert';
import 'package:http/http.dart' as http;

class IQDRateService {
  static const String _baseUrl = 'https://usd-ih41.onrender.com/api';
  static const String _apiKey  = 'YOUR_API_KEY';

  static Map<String, String> get _headers => {
    'X-API-Key': _apiKey,
    'Content-Type': 'application/json',
  };

  /// Fetch the latest Erbil USD/IQD rate.
  static Future<ExchangeRate> getLatestRate() async {
    final uri      = Uri.parse('$_baseUrl/rate/latest');
    final response = await http.get(uri, headers: _headers)
        .timeout(const Duration(seconds: 10));

    _checkStatus(response);
    return ExchangeRate.fromJson(jsonDecode(response.body));
  }

  /// Convert USD to IQD.
  static Future<ConversionResult> usdToIqd(double amount) async {
    final uri = Uri.parse('$_baseUrl/convert/usd-to-iqd')
        .replace(queryParameters: {'amount': amount.toString()});
    final response = await http.get(uri, headers: _headers)
        .timeout(const Duration(seconds: 10));

    _checkStatus(response);
    return ConversionResult.fromJson(jsonDecode(response.body));
  }

  /// Fetch historical rates. days: 1, 7, 30, or 90.
  static Future<List<HistoricalRate>> getHistory(int days) async {
    final uri = Uri.parse('$_baseUrl/rate/history')
        .replace(queryParameters: {'days': days.toString()});
    final response = await http.get(uri, headers: _headers)
        .timeout(const Duration(seconds: 10));

    _checkStatus(response);
    final List<dynamic> rates = jsonDecode(response.body)['rates'];
    return rates.map(HistoricalRate.fromJson).toList();
  }

  static void _checkStatus(http.Response response) {
    switch (response.statusCode) {
      case 200: return;
      case 401: throw Exception('Invalid API key.');
      case 429: throw Exception('Rate limit exceeded. Try again later.');
      default:
        final body = jsonDecode(response.body);
        throw Exception('API error ${response.statusCode}: ${body['detail']}');
    }
  }
}
```

---

## Data Models

```dart
// lib/models/exchange_rate.dart

class ExchangeRate {
  final int average;
  final int penzi;
  final int sur;
  final int dailyChange;
  final String lastUpdated;

  const ExchangeRate({
    required this.average,
    required this.penzi,
    required this.sur,
    required this.dailyChange,
    required this.lastUpdated,
  });

  factory ExchangeRate.fromJson(Map<String, dynamic> json) => ExchangeRate(
    average:     json['average'],
    penzi:       json['penzi'],
    sur:         json['sur'],
    dailyChange: json['daily_change'] ?? 0,
    lastUpdated: json['last_updated'],
  );
}

class ConversionResult {
  final double usd;
  final int iqd;

  const ConversionResult({required this.usd, required this.iqd});

  factory ConversionResult.fromJson(Map<String, dynamic> json) =>
      ConversionResult(usd: json['usd'].toDouble(), iqd: json['iqd']);
}

class HistoricalRate {
  final String date;
  final int average;

  const HistoricalRate({required this.date, required this.average});

  static HistoricalRate fromJson(Map<String, dynamic> json) =>
      HistoricalRate(date: json['date'], average: json['average']);
}
```

---

## UI Widget — Live Rate Card

```dart
// lib/widgets/rate_card.dart

import 'package:flutter/material.dart';
import '../services/iqdrate_service.dart';
import '../models/exchange_rate.dart';

class RateCard extends StatefulWidget {
  const RateCard({super.key});

  @override
  State<RateCard> createState() => _RateCardState();
}

class _RateCardState extends State<RateCard> {
  ExchangeRate? _rate;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchRate();
  }

  Future<void> _fetchRate() async {
    setState(() { _loading = true; _error = null; });
    try {
      final rate = await IQDRateService.getLatestRate();
      setState(() { _rate = rate; _loading = false; });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return Text('Error: $_error');

    final rate = _rate!;
    final changeColor = rate.dailyChange >= 0 ? Colors.green : Colors.red;
    final changePrefix = rate.dailyChange >= 0 ? '+' : '';

    return Card(
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            const Text('USD / IQD — Erbil',
                style: TextStyle(fontSize: 14, color: Colors.grey)),
            const SizedBox(height: 8),
            Text('${rate.average.toStringAsFixed(0)} IQD',
                style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold)),
            Text('$changePrefix${rate.dailyChange} today',
                style: TextStyle(color: changeColor)),
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: _fetchRate,
              icon: const Icon(Icons.refresh, size: 16),
              label: const Text('Refresh'),
            ),
          ],
        ),
      ),
    );
  }
}
```

---

## WebSocket — Live Feed

```dart
// lib/services/iqdrate_websocket.dart

import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';

class IQDRateWebSocket {
  static const String _wsUrl = 'wss://usd-ih41.onrender.com/api/ws';

  WebSocketChannel? _channel;

  void connect(void Function(Map<String, dynamic> rate) onRate) {
    _channel = WebSocketChannel.connect(Uri.parse(_wsUrl));

    _channel!.stream.listen(
      (message) {
        final data = jsonDecode(message as String);
        if (data is Map && data.containsKey('average')) {
          onRate(data);
        }
      },
      onDone: () {
        // Auto-reconnect after 5 seconds
        Future.delayed(const Duration(seconds: 5), () => connect(onRate));
      },
    );
  }

  void disconnect() => _channel?.sink.close();
}
```
