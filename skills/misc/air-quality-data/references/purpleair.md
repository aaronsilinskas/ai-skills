# PurpleAir API Reference

**Base URL:** `https://api.purpleair.com/v1/`  
**Developer dashboard:** https://develop.purpleair.com/  
**Community:** https://community.purpleair.com/c/data/api/

## Authentication

Preferred: `X-API-Key: {key}` HTTP header  
Alternative: `?api_key={key}` query param or JSON body field

READ key for GET requests; WRITE key for POST/DELETE.

## Points System

Each API call costs points. Your organization starts with 1,000,000 free points. Sensor owners receive free points for querying their own sensors.

Approximate costs:
- Single sensor current data: ~1 point per field requested
- Multi-sensor query: scales with number of sensors × fields
- History: higher cost due to data volume

Check balance: `GET /organization` with READ key.

## Full Endpoint Reference

### Check API Key
```
GET /v1/keys
X-API-Key: {READ key}
```

### Get Single Sensor (Latest)
```
GET /v1/sensors/{sensor_index}
X-API-Key: {READ key}

Query params:
  fields    comma-separated field names (see below)
  read_key  required for private sensors
```
Rate limit: 100ms

### Get Multiple Sensors (Latest)
```
GET /v1/sensors
X-API-Key: {READ key}

Query params:
  fields          required — comma-separated
  location_type   0=outside, 1=inside
  read_keys       comma-separated, for private sensors
  show_only       comma-separated sensor_index list
  modified_since  unix timestamp; only return newer sensors
  max_age         seconds; default 604800 (7 days)
  nwlat, nwlng    bounding box NW corner
  selat, selng    bounding box SE corner
```
Rate limit: 500ms

### Get Sensor History (JSON)
```
GET /v1/sensors/{sensor_index}/history
X-API-Key: {READ key}

Query params:
  fields           required
  start_timestamp  unix seconds or ISO 8601
  end_timestamp    unix seconds or ISO 8601
  average          minutes: 0 (raw), 10, 30, 60, 360, 1440
  privacy          auto | public | private | both
  read_key         for private sensors
```
Rate limit: 1000ms

### Get Sensor History (CSV)
Same as above but at `/history/csv`. Returns `headers` and `data` arrays.
Rate limit: 1000ms

## Sensor Data Fields

### Station / Status
| Field | Type | Description |
|-------|------|-------------|
| `sensor_index` | int | Unique sensor ID |
| `name` | string | Sensor name from registration |
| `latitude` | float | |
| `longitude` | float | |
| `altitude` | float | Feet |
| `location_type` | int | 0=outside, 1=inside |
| `private` | int | 0=public, 1=private |
| `last_seen` | unix | Last data received |
| `confidence` | int | 0–100%, channel A/B agreement |
| `model` | string | Device model |

### Environmental
| Field | Type | Description |
|-------|------|-------------|
| `humidity` | int | % — inside sensor housing, not ambient |
| `temperature` | int | °F — inside sensor housing, not ambient |
| `pressure` | float | Millibars |
| `voc` | float | VOC in Bosch IAQ units (EXPERIMENTAL) |
| `ozone1` | float | Ozone PPB (only ~12 sensors have this) |

### PM2.5 Variants
| Field | Description |
|-------|-------------|
| `pm2.5` | Auto-selects ATM (outdoor) or CF=1 (indoor); avg A+B, excludes downgraded |
| `pm2.5_a` / `pm2.5_b` | Channel A / B individually |
| `pm2.5_atm` | Atmospheric variant — for outdoor sensors |
| `pm2.5_atm_a` / `pm2.5_atm_b` | Channel A/B ATM |
| `pm2.5_cf_1` | CF=1 variant — for indoor sensors |
| `pm2.5_alt` | Alt variant from particle counts; often closer to FEM monitors |
| `pm2.5_10minute` | 10-min running average |
| `pm2.5_30minute` | 30-min running average |
| `pm2.5_60minute` | 60-min running average |
| `pm2.5_6hour` | 6-hour running average |
| `pm2.5_24hour` | 24-hour running average |
| `pm2.5_1week` | 1-week running average |

### PM1.0 and PM10
Same variant pattern as PM2.5: `pm1.0`, `pm1.0_atm`, `pm1.0_cf_1`, `pm10.0`, `pm10.0_atm`, etc.

### Particle Counts (particles/deciliter)
`0.3_um_count`, `0.5_um_count`, `1.0_um_count`, `2.5_um_count`, `5.0_um_count`, `10.0_um_count`

## EPA Correction Factors for PM2.5

Raw PurpleAir PM2.5 values tend to read 20–50% higher than co-located FEM monitors. Apply corrections before displaying to users who expect regulatory-equivalent values.

```python
# EPA 2021 US-Wide correction
# Input: pm25_cf1 (CF=1 variant), rh (relative humidity 0-100)
# Best for non-smoke conditions
def epa_correction(pm25_cf1: float, rh: float) -> float:
    return 0.534 * pm25_cf1 - 0.0844 * rh + 5.604

# LRAPA correction (Lane Regional Air Protection Agency)
# Good for wildfire smoke
def lrapa(pm25_cf1: float) -> float:
    return max(0, 0.5 * pm25_cf1 - 0.66)

# AQandU correction
# Originally for general use; still used by some tools
def aqandu(pm25_atm: float) -> float:
    return (pm25_atm + 5.75) / 1.728
```

Note: These are approximations. For scientific work, validate against local FEM monitors.

## Multi-Sensor Response Parsing

```python
resp = requests.get(url, headers=headers, params=params).json()
field_map = {f: i for i, f in enumerate(resp["fields"])}
sensors = [
    {f: row[field_map[f]] for f in resp["fields"]}
    for row in resp["data"]
]
```

## Channel Flags

`channel_state` and `channel_flags` indicate sensor health:
- `Normal` — both channels operating
- `A-Downgraded` / `B-Downgraded` — one channel excluded from averages
- `A+B-Downgraded` — avoid using this sensor's data

Only use sensors where `confidence >= 80` for reliable readings.
