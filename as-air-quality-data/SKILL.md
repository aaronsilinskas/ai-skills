---
name: as-air-quality-data
description: "Retrieve live air quality data by running scripts from this skill. Use this skill whenever the user wants to fetch, check, or compare air quality data, AQI values, PM2.5, PM10, or pollutant levels for any location — even if they just say 'what's the air quality near me' or 'is it safe to go outside'. Also use when combining data across multiple sources or applying correction factors to sensor readings. Runs Python scripts directly against EPA AirNow, PurpleAir, and IQAir — no API knowledge required."
---

# Air Quality Data

Fetch live air quality data by running Python scripts from this skill's `scripts/` directory. All scripts output JSON to stdout and read API keys from environment variables.

`<skill-path>` below refers to the directory containing this SKILL.md file.

## Setup

Store API keys in `~/.config/as-air-quality-data/.env`:

```bash
mkdir -p ~/.config/as-air-quality-data
# Warning: this overwrites the file. To update a single key, edit the file directly instead.
cat > ~/.config/as-air-quality-data/.env << 'EOF'
AIRNOW_API_KEY=your_key_here
PURPLEAIR_API_KEY=your_key_here
IQAIR_API_KEY=your_key_here
EOF
```

You only need keys for the sources you'll use. Environment variables take precedence over the file.

| Variable | Register at | Cost |
|---|---|---|
| `AIRNOW_API_KEY` | https://docs.airnowapi.org/ | Free |
| `PURPLEAIR_API_KEY` | https://develop.purpleair.com/ | Free (1M points) |
| `IQAIR_API_KEY` | https://dashboard.iqair.com/personal/api-keys | Free community tier |

Install the one dependency if needed: `pip install requests`

---

## Which script to use

| Need | Script |
|---|---|
| Official US/Canada/Mexico AQI, forecasts, historical | `fetch_airnow.py` |
| Neighborhood-level PM2.5, wildfire smoke, dense local sensors | `fetch_purpleair.py` |
| Global city/station data + weather | `fetch_iqair.py` |

---

## fetch_airnow.py

Query EPA AirNow for current AQI, forecasts, or historical data.

```bash
# Current AQI by zip code
python <skill-path>/scripts/fetch_airnow.py --zip 94103

# Current AQI by lat/lng
python <skill-path>/scripts/fetch_airnow.py --lat 37.77 --lng -122.41

# Forecast (defaults to today; provide --date for another day YYYY-MM-DD)
python <skill-path>/scripts/fetch_airnow.py --zip 94103 --mode forecast --date 2024-03-16

# Historical (requires --date)
python <skill-path>/scripts/fetch_airnow.py --zip 94103 --mode historical --date 2024-03-10

# Wider search radius in miles (default 25)
python <skill-path>/scripts/fetch_airnow.py --zip 94103 --distance 50
```

**Output:** Array of observations, one per pollutant. Multiple entries are normal — each has `ParameterName`, `AQI`, and `Category.Name`. The entry with the highest `AQI` is the overall air quality.

**AQI scale:** Good (0–50) · Moderate (51–100) · Unhealthy for Sensitive Groups (101–150) · Unhealthy (151–200) · Very Unhealthy (201–300) · Hazardous (301+)

---

## fetch_purpleair.py

Query PurpleAir for hyperlocal PM2.5 from community sensors near a location.

```bash
# Sensors near a lat/lng (default 5-mile radius)
python <skill-path>/scripts/fetch_purpleair.py --lat 37.77 --lng -122.41

# Adjust search radius in miles
python <skill-path>/scripts/fetch_purpleair.py --lat 37.77 --lng -122.41 --radius 2

# Single sensor by index (find index from a nearby-sensors query)
python <skill-path>/scripts/fetch_purpleair.py --sensor-index 12345

# Historical data for a sensor (last 24 hours, hourly averages)
python <skill-path>/scripts/fetch_purpleair.py --sensor-index 12345 --history --hours 24

# Historical data for a date range (daily averages — one API call)
python <skill-path>/scripts/fetch_purpleair.py --sensor-index 12345 --history --start-date 2025-01-01 --end-date 2025-12-31 --average 1440

# Last 7 days at 6-hour averages
python <skill-path>/scripts/fetch_purpleair.py --sensor-index 12345 --history --hours 168 --average 360
```

**Output:** For nearby sensors: array with `name`, `latitude`, `longitude`, `pm25_corrected` (EPA correction applied), `pm25_raw`, `aqi_category`. For single sensor: full reading with humidity and temperature included.

**Note on correction:** `pm25_corrected` uses the EPA 2021 US-wide formula. Raw PurpleAir values tend to read 20–50% high compared to regulatory monitors. Always use `pm25_corrected` for health guidance.

---

## fetch_iqair.py

Query IQAir for city-level AQI and weather. Works globally; free plan limited to 500 calls/day.

```bash
# City by name
python <skill-path>/scripts/fetch_iqair.py --city "Los Angeles" --state California --country USA

# Use IP geolocation (unreliable in cloud/server environments)
python <skill-path>/scripts/fetch_iqair.py --nearest

# Discover available locations
python <skill-path>/scripts/fetch_iqair.py --list-states --country USA
python <skill-path>/scripts/fetch_iqair.py --list-cities --state California --country USA
```

**Output:** Current AQI (US scale), main pollutant, temperature (°C), humidity, wind speed and direction.

---

## analyze_history.py

Summarize one or more PurpleAir history JSON files (produced by `fetch_purpleair.py --history`) into annual statistics.

```bash
# Analyze a single sensor history file
python <skill-path>/scripts/analyze_history.py sensor_12345.json

# Analyze multiple files at once (glob supported)
python <skill-path>/scripts/analyze_history.py /tmp/pgh_*.json
```

**Input:** JSON files from `fetch_purpleair.py --history`. Accepts both formats:
- Single-sensor object: `{"sensor_index": N, "history": [{...}, ...]}`
- Raw list: `[{...}, ...]`

**Output per file:** number of valid days, mean PM2.5 (µg/m³), day counts and percentages for Good / Moderate / USG+, and the 5 worst daily values.

**Typical workflow:**
```bash
# 1. Fetch a year of daily averages for a sensor
python <skill-path>/scripts/fetch_purpleair.py --sensor-index 12345 \
  --history --start-date 2025-01-01 --end-date 2025-12-31 --average 1440 \
  > sensor_12345.json

# 2. Summarize
python <skill-path>/scripts/analyze_history.py sensor_12345.json
```

---

## Presenting results

**For current conditions:** Lead with the AQI number and category — e.g., "AQI 52 — Moderate". Follow with the dominant pollutant and a one-sentence health takeaway.

**For historical data:** Group daily readings by month using the `time_stamp` field (Unix seconds) present in the history JSON, then report monthly average and maximum PM2.5 (µg/m³). Open with the single worst month, then show the full table:

```
Month       Avg PM2.5   Max PM2.5
Jan 2025    8.2 µg/m³   23.1 µg/m³
Feb 2025    9.7 µg/m³   31.4 µg/m³
…
```

---

## Comparing results across sources

- **AirNow and IQAir** both use the official US EPA AQI scale — values are directly comparable.
- **PurpleAir** `pm25_corrected` is converted to AQI-equivalent and comparable after correction.
- If sources disagree by more than ~30 AQI points, trust AirNow or IQAir — they use validated instruments. PurpleAir is best used for spatial density (finding the worst microzone) rather than absolute values.
- Timestamps: IQAir uses UTC ISO 8601; AirNow uses local time with a timezone label.  
