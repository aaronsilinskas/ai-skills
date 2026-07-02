# OpenAQ API Reference (v3)

**Base URL:** `https://api.openaq.org/v3`
**Registration:** https://openaq.org/register
**Auth:** send the key in an `X-API-Key` request header (not a query param).
**Supported regions:** Global. Aggregates official government/regulatory monitors
worldwide — especially valuable where PurpleAir is sparse (Japan, Korea, most of
Europe).

PM2.5 is parameter ID **2** (stable in v3). `scripts/fetch_openaq.py` filters
`/locations` sensors to this ID.

## Full Endpoint Reference

### Find monitoring locations near a coordinate
```
GET /v3/locations
  ?coordinates={lat},{lon}
  &radius={meters, max 25000}
  &limit={default 50}
  &page={1-based}
Header: X-API-Key: {key}
```
Each result carries a `sensors` array; pick the sensor whose
`parameter.id == 2` for PM2.5. `isMonitor: true` marks a government
regulatory station; anything else is a lower-quality community sensor.

### Fetch measurements for a single sensor
```
GET /v3/sensors/{sensor_id}/measurements
  ?datetime_from={YYYY-MM-DDT00:00:00Z}
  &datetime_to={YYYY-MM-DDT23:59:59Z}
  &limit={default 500}
  &page={1-based}
Header: X-API-Key: {key}
```
Measurements are hourly; `fetch_openaq.py` averages them into daily values.
Omit the datetime bounds to pull all available history.

## Pagination

List endpoints return `meta.found` (total available) and a `results` array.
Walk `page=1,2,…` until `len(collected) >= found` or a page comes back empty.
`fetch_openaq.py` caps this at `--page-limit` pages (default 25 for history,
~12,500 hourly readings) to bound long pulls.

## Response Fields

### `/locations` result
| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Location ID (not the sensor ID) |
| `name` | string | Station/location name |
| `isMonitor` | bool | `true` = government regulatory station |
| `provider.name` | string | Operating network/provider |
| `coordinates.latitude` / `.longitude` | float | Station position |
| `distance` | float | Metres from the query coordinate |
| `sensors[].id` | int | **Sensor ID — use this with `/sensors/{id}/measurements`** |
| `sensors[].parameter.id` | int | Pollutant ID (`2` = PM2.5) |
| `sensors[].lastUpdated` | string | ISO timestamp of the latest reading |

### `/sensors/{id}/measurements` result
| Field | Type | Description |
|-------|------|-------------|
| `value` | float | PM2.5 concentration in µg/m³ (raw, uncorrected) |
| `period.datetimeFrom.local` | string | Local ISO timestamp for the reading |
| `period.datetimeFrom.utc` | string | UTC ISO timestamp (fallback) |

## Notes

- Values are **raw regulatory-grade µg/m³** — no correction factor is needed
  (unlike PurpleAir). Directly comparable to AirNow reference monitors.
- Ingestion lag: some national networks (e.g. Japan's MOE stations) lag 6–8
  months, so the most recent months may be missing.
- Use `sensor_id` (from a location's `sensors[]`), **not** `location_id`, when
  fetching history.
- Distinguish the two IDs: `/locations` returns both; only the sensor ID indexes
  the measurements endpoint.
