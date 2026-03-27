# IQAir (AirVisual) API Reference

**Docs:** https://api-docs.iqair.com/  
**Base URL:** `https://api.airvisual.com/v2/`  
**Key registration:** https://dashboard.iqair.com/personal/api-keys  
**Auth:** `?key={api_key}` query parameter on all requests

## Plan Comparison

| Feature | Community (Free) | Startup | Enterprise |
|---------|-----------------|---------|------------|
| Calls/minute | 5 | 100 | 1,000 |
| Calls/day | 500 | 100,000 | 1,000,000 |
| Calls/month | 10,000 | 1,000,000 | 10,000,000 |
| City/station AQI | ✓ | ✓ | ✓ |
| AQI (US + China) | ✓ | ✓ | ✓ |
| Weather data | ✓ | ✓ | ✓ |
| Pollutant concentrations | – | ✓ | ✓ |
| Hourly forecast (72hr) | – | – | ✓ |
| Daily forecast (7-day) | – | – | ✓ |
| 48hr historical AQI | – | – | ✓ |
| Nearest station | – | ✓ | ✓ |

## Endpoints

### Discovery (all plans)
```
GET /countries?key={key}
GET /states?country={USA}&key={key}
GET /cities?state={California}&country={USA}&key={key}
GET /stations?city={Los Angeles}&state={California}&country={USA}&key={key}
```

### Current Data by City (all plans)
```
GET /city?city={city}&state={state}&country={country}&key={key}
```
Returns current weather + AQI. Pollutant concentrations require Startup+.

### Nearest City by IP (all plans)
```
GET /nearest_city?key={key}
```
Locates by IP — useful for quick defaults, unreliable in server contexts.

### Nearest Monitoring Station (Startup+)
```
GET /nearest_station?lat={lat}&lon={lon}&key={key}
```

### Specific Station (Startup+)
```
GET /station?station={name}&city={city}&state={state}&country={country}&key={key}
```

### City Ranking (Enterprise only)
```
GET /city_ranking?key={key}
```
Returns most polluted cities globally.

## Response Structure

```json
{
  "status": "success",
  "data": {
    "city": "San Francisco",
    "state": "California",
    "country": "USA",
    "location": {
      "type": "Point",
      "coordinates": [-122.41, 37.77]
    },
    "current": {
      "weather": {
        "ts": "2024-03-15T14:00:00.000Z",
        "tp": 18,          // temperature °C
        "tp_min": 12,      // min temperature (forecast only)
        "pr": 1013,        // pressure hPa
        "hu": 65,          // humidity %
        "ws": 3.5,         // wind speed m/s
        "wd": 270,         // wind direction degrees (N=0, E=90)
        "ic": "04d",       // weather icon code
        "heatIndex": 19    // apparent temperature °C
      },
      "pollution": {
        "ts": "2024-03-15T14:00:00.000Z",
        "aqius": 42,       // US EPA AQI
        "mainus": "p2",    // main pollutant (US)
        "aqicn": 15,       // China AQI
        "maincn": "p2",    // main pollutant (China)
        "p2": { "conc": 10.5, "aqius": 42, "aqicn": 15 },
        "p1": { "conc": 18.0, "aqius": 14, "aqicn": 12 },
        "o3": { "conc": 28.0, "aqius": 15, "aqicn": 14 },
        "n2": { "conc": 12.0, "aqius": 11, "aqicn": 9 },
        "s2": { "conc": 1.2,  "aqius": 2,  "aqicn": 1 },
        "co": { "conc": 0.4,  "aqius": 5,  "aqicn": 4 }
      }
    }
  }
}
```

## Pollutant Key Reference

| Key | Pollutant | Unit |
|-----|-----------|------|
| `p2` | PM2.5 | µg/m³ |
| `p1` | PM10 | µg/m³ |
| `o3` | Ozone (O3) | ppb |
| `n2` | Nitrogen dioxide (NO2) | ppb |
| `s2` | Sulfur dioxide (SO2) | ppb |
| `co` | Carbon monoxide (CO) | ppm |

CO units may occasionally be µg/m³ instead of ppm — check `units` field in response.

## Return Codes

Always check `status` field in response body:

| Code | Meaning |
|------|---------|
| `success` | OK |
| `call_limit_reached` | Minute or monthly quota hit |
| `api_key_expired` | Key needs renewal |
| `incorrect_api_key` | Wrong key |
| `ip_location_failed` | `/nearest_city` couldn't geolocate |
| `no_nearest_station` | No station within radius |
| `feature_not_available` | Endpoint requires higher plan |
| `too_many_requests` | >10 calls/second |

## Notes

- Timestamps are UTC ISO 8601 — convert to local time for display.
- Stations update approximately once per hour; calls within the same hour return cached data.
- The `mainus` field tells you which pollutant is driving the overall AQI — useful for health messaging.
- IQAir applies ML-based validation and calibration, making it more reliable than raw sensor networks for regulatory comparison.
- `nearest_city` by IP is unreliable in cloud/server environments — pass explicit coordinates when possible.
