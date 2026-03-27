---
name: as-air-quality-data
description: "Retrieve live air quality data by running scripts from this skill. Use this skill whenever the user wants to fetch, check, or compare air quality data, AQI values, PM2.5, PM10, or pollutant levels for any location — even if they just say 'what's the air quality near me' or 'is it safe to go outside'. Works globally including non-US cities (Tokyo, Seoul, London, Paris, etc.) via OpenAQ government monitors. Also use when combining data across multiple sources or applying correction factors to sensor readings. Runs Python scripts directly against EPA AirNow, PurpleAir, IQAir, and OpenAQ — no API knowledge required."
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

| Variable            | Register at                                   | Cost                |
| ------------------- | --------------------------------------------- | ------------------- |
| `AIRNOW_API_KEY`    | https://docs.airnowapi.org/                   | Free                |
| `PURPLEAIR_API_KEY` | https://develop.purpleair.com/                | Free (1M points)    |
| `IQAIR_API_KEY`     | https://dashboard.iqair.com/personal/api-keys | Free community tier |
| `OPENAQ_API_KEY`    | https://openaq.org/register                   | Free                |

Install the one dependency if needed: `pip install requests`

---

## Which script to use

| Need                                                            | Script               |
| --------------------------------------------------------------- | -------------------- |
| Official US/Canada/Mexico AQI, forecasts, historical            | `fetch_airnow.py`    |
| Neighborhood-level PM2.5, wildfire smoke, dense local sensors   | `fetch_purpleair.py` |
| Global city/station data + weather                              | `fetch_iqair.py`     |
| Official government PM2.5 monitors, global (esp. non-US cities) | `fetch_openaq.py`    |

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

**History limit:** `--hours` cannot exceed 8760 (1 year). `--start-date`/`--end-date` range cannot exceed 365 days.

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

## fetch_openaq.py

Query OpenAQ for official government PM2.5 monitors worldwide. Especially useful for countries with sparse PurpleAir coverage — Japan, Korea, and most of Europe report regulatory-grade data through OpenAQ. Data has a 6–8 month ingestion lag in some countries (MOE stations in Japan, for example), so recent months may be missing.

Two subcommands: **`sensors`** to discover monitors near a location, and **`history`** to fetch all available measurements for a single sensor.

```bash
# Find PM2.5 monitors near Tokyo (default 15 km radius)
python <skill-path>/scripts/fetch_openaq.py sensors --lat 35.685 --lon 139.751

# Widen search radius
python <skill-path>/scripts/fetch_openaq.py sensors --lat 33.590 --lon 130.401 --radius 25

# Include non-official community sensors (excluded by default)
python <skill-path>/scripts/fetch_openaq.py sensors --lat 35.685 --lon 139.751 --all

# Fetch all available history for a sensor (up to 25 pages = ~12,500 hourly readings)
python <skill-path>/scripts/fetch_openaq.py history --sensor-id 6515867

# Restrict to a date range and include daily statistics summary
python <skill-path>/scripts/fetch_openaq.py history --sensor-id 6515867 \
    --start-date 2024-01-01 --end-date 2024-12-31 --stats

# Fetch more history (raise page cap for sensors with years of data)
python <skill-path>/scripts/fetch_openaq.py history --sensor-id 6515867 --page-limit 50
```

**History limit:** `--start-date` to `--end-date` range cannot exceed 365 days. If no end date is given, the range is measured from `--start-date` to today.

**sensors output:** Array of `{sensor_id, location_id, name, provider, lat, lon, distance_km, last_updated}`, sorted by distance. Use `sensor_id` (not `location_id`) with the `history` subcommand.

**history output:** `{sensor_id, date_from, date_to, raw_measurements, daily_values}` where `daily_values` is a dict of `{"YYYY-MM-DD": avg_pm25_float}`. Add `--stats` for a full summary including monthly averages, day-count breakdowns, and worst-5 days.

**Note on data:** OpenAQ returns raw, uncorrected PM2.5 from regulatory instruments (these are already accurate — no correction factor needed). `isMonitor: true` locations are government stations; the `--all` flag also includes lower-quality community sensors.

**Typical workflow for a new city:**

```bash
# 1. Find nearby government monitors
python <skill-path>/scripts/fetch_openaq.py sensors --lat 35.685 --lon 139.751 > sensors.json

# 2. Pick a sensor with a recent last_updated date and reasonable distance
# 3. Fetch its history with stats
python <skill-path>/scripts/fetch_openaq.py history --sensor-id 6516560 --stats
```

---

## analyze_history.py

Summarize PM2.5 history JSON files into monthly and annual statistics. Accepts output from both `fetch_purpleair.py --history` and `fetch_openaq.py history`.

```bash
# Analyze a single file
python <skill-path>/scripts/analyze_history.py sensor_12345.json

# Analyze multiple files at once (glob supported)
python <skill-path>/scripts/analyze_history.py /tmp/sensors_*.json
```

**Accepted formats:**

- PurpleAir: `{"sensor_index": N, "history": [{time_stamp, pm2.5_cf_1_corrected, ...}]}` or bare list
- OpenAQ: `{"sensor_id": N, "daily_values": {"YYYY-MM-DD": float}}` (from `fetch_openaq.py history`)

Note: use `fetch_openaq.py history --stats` if you just need a quick summary for a single OpenAQ sensor — it computes stats inline without a separate file.

**Output per file:** worst month (shown first), monthly avg/max table, annual mean, Good/Moderate/USG+ day counts, 5 worst days.

**PurpleAir workflow:**

```bash
python <skill-path>/scripts/fetch_purpleair.py --sensor-index 12345 \
  --history --start-date 2025-01-01 --end-date 2025-12-31 --average 1440 \
  > sensor_12345.json
python <skill-path>/scripts/analyze_history.py sensor_12345.json
```

**OpenAQ workflow:**

```bash
python <skill-path>/scripts/fetch_openaq.py history --sensor-id 6516560 \
  --start-date 2024-01-01 --end-date 2024-12-31 > tokyo_sensor.json
python <skill-path>/scripts/analyze_history.py tokyo_sensor.json
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
- **OpenAQ** returns raw PM2.5 µg/m³ from government regulatory instruments — no correction needed. Values are directly comparable to AirNow reference monitors.
- If sources disagree by more than ~30 AQI points, trust AirNow, IQAir, or OpenAQ — they use validated instruments. PurpleAir is best used for spatial density (finding the worst microzone) rather than absolute values.
- Timestamps: IQAir uses UTC ISO 8601; AirNow uses local time with a timezone label.
