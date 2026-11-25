#!/usr/bin/env python3
"""Fetch air quality data from the PurpleAir API.

Reads PURPLEAIR_API_KEY from the environment or ~/.config/as-air-quality-data/.env.
Applies the EPA 2021 PM2.5 correction factor.
Outputs JSON to stdout.
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

import requests

ENV_FILE = Path.home() / ".config" / "as-air-quality-data" / ".env"


def load_env_file():
    """Load KEY=VALUE pairs from ENV_FILE into os.environ. Existing env vars take precedence."""
    if not ENV_FILE.exists():
        return
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

BASE_URL = "https://api.purpleair.com/v1"

# Fields to request for nearby-sensor and single-sensor queries
SENSOR_FIELDS = "name,latitude,longitude,pm2.5_cf_1,pm2.5_cf_1_a,pm2.5_cf_1_b,humidity,temperature,pressure,last_seen"
HISTORY_FIELDS = "pm2.5_cf_1,humidity,temperature"


def headers(api_key):
    return {"X-API-Key": api_key}


def epa_correction(pm25_cf1, rh):
    """EPA 2021 US-wide PM2.5 correction formula."""
    return 0.534 * pm25_cf1 - 0.0844 * rh + 5.604


def parse_sensor_row(field_index, row):
    """Convert a columnar PurpleAir sensor row to a dict."""
    entry = {field: row[idx] for field, idx in field_index.items()}
    pm25_raw = entry.get("pm2.5_cf_1")
    rh = entry.get("humidity")
    if pm25_raw is not None and rh is not None:
        entry["pm2.5_cf_1_corrected"] = round(epa_correction(pm25_raw, rh), 2)
    return entry


def fetch(path, params=None, api_key=None):
    url = f"{BASE_URL}/{path}"
    try:
        resp = requests.get(url, params=params, headers=headers(api_key), timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        print(
            json.dumps({"error": str(e), "status_code": resp.status_code}),
            file=sys.stderr,
        )
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


def bounding_box(lat, lng, radius_miles):
    """Return (nwlng, selat, selng, nwlat) bounding box for radius in miles."""
    lat_deg = radius_miles / 69.0
    lng_deg = radius_miles / (69.0 * math.cos(math.radians(lat)))
    return (
        round(lng - lng_deg, 6),
        round(lat - lat_deg, 6),
        round(lng + lng_deg, 6),
        round(lat + lat_deg, 6),
    )


def main():
    load_env_file()
    api_key = os.environ.get("PURPLEAIR_API_KEY")
    if not api_key:
        print(
            json.dumps({"error": "PURPLEAIR_API_KEY environment variable not set"}),
            file=sys.stderr,
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Fetch PM2.5 data from PurpleAir")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sensor-index", type=int, help="Single sensor index")
    mode.add_argument(
        "--lat", type=float, help="Center latitude for nearby search (use with --lng)"
    )
    parser.add_argument(
        "--lng", type=float, help="Center longitude for nearby search (use with --lat)"
    )
    parser.add_argument(
        "--radius",
        type=float,
        default=5.0,
        help="Search radius in miles for nearby search (default: 5)",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Fetch historical data (only valid with --sensor-index)",
    )
    parser.add_argument(
        "--hours",
        type=int,
        help="Number of hours of history to return (default: 24). Mutually exclusive with --start-date/--end-date.",
    )
    parser.add_argument(
        "--start-date",
        help="Start date for history range (YYYY-MM-DD). Use with --end-date.",
    )
    parser.add_argument(
        "--end-date",
        help="End date for history range, inclusive (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--average",
        type=int,
        default=60,
        choices=[0, 10, 30, 60, 360, 1440],
        help="Averaging period in minutes: 0=raw, 10, 30, 60 (default), 360, 1440=daily",
    )
    args = parser.parse_args()

    if args.lat is not None and args.lng is None:
        parser.error("--lng is required when using --lat")

    if args.history and args.sensor_index is None:
        parser.error("--history requires --sensor-index")

    if args.start_date and args.hours:
        parser.error("--start-date and --hours are mutually exclusive")

    if args.hours and args.hours > 8760:
        parser.error("--hours cannot exceed 8760 (1 year)")

    if args.start_date:
        from datetime import datetime, timezone
        _start = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        _end = (
            datetime.strptime(args.end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if args.end_date
            else datetime.now(timezone.utc)
        )
        if (_end - _start).days > 365:
            parser.error("date range cannot exceed 1 year (365 days)")

    if args.sensor_index is not None:
        if args.history:
            import time as _time
            from datetime import datetime, timezone, timedelta

            if args.start_date:
                start_dt = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                start_ts = int(start_dt.timestamp())
                if args.end_date:
                    end_dt = datetime.strptime(args.end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
                else:
                    end_dt = datetime.now(timezone.utc)
                end_ts = int(end_dt.timestamp())
            else:
                hours = args.hours if args.hours else 24
                end_ts = int(_time.time())
                start_ts = end_ts - hours * 3600

            params = {
                "fields": HISTORY_FIELDS,
                "average": args.average,
                "start_timestamp": start_ts,
                "end_timestamp": end_ts,
            }
            data = fetch(
                f"sensors/{args.sensor_index}/history", params=params, api_key=api_key
            )
            field_index = {f: i for i, f in enumerate(data.get("fields", []))}
            rows = [parse_sensor_row(field_index, row) for row in data.get("data", [])]
            print(
                json.dumps(
                    {"sensor_index": args.sensor_index, "history": rows}, indent=2
                )
            )
        else:
            params = {"fields": SENSOR_FIELDS}
            data = fetch(f"sensors/{args.sensor_index}", params=params, api_key=api_key)
            sensor = data.get("sensor", {})
            pm25_raw = sensor.get("pm2.5_cf_1")
            rh = sensor.get("humidity")
            if pm25_raw is not None and rh is not None:
                sensor["pm2.5_cf_1_corrected"] = round(epa_correction(pm25_raw, rh), 2)
            print(json.dumps(sensor, indent=2))
    else:
        nwlng, selat, selng, nwlat = bounding_box(args.lat, args.lng, args.radius)
        params = {
            "fields": SENSOR_FIELDS,
            "nwlng": nwlng,
            "nwlat": nwlat,
            "selng": selng,
            "selat": selat,
        }
        data = fetch("sensors", params=params, api_key=api_key)
        field_index = {f: i for i, f in enumerate(data.get("fields", []))}
        sensors = [parse_sensor_row(field_index, row) for row in data.get("data", [])]
        print(json.dumps({"count": len(sensors), "sensors": sensors}, indent=2))


if __name__ == "__main__":
    main()
