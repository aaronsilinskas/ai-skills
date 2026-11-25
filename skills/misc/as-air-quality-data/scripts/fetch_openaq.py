#!/usr/bin/env python3
"""Fetch air quality data from the OpenAQ v3 API.

Queries official government monitoring stations worldwide. Particularly useful
for countries with sparse PurpleAir coverage (Japan, Korea, Europe) where national
environment ministries operate regulatory-grade PM2.5 monitors aggregated by OpenAQ.

Reads OPENAQ_API_KEY from the environment or ~/.config/as-air-quality-data/.env.
Outputs JSON to stdout. Requires no third-party packages (uses urllib).

Register for a free API key at https://openaq.org/register
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ENV_FILE = Path.home() / ".config" / "as-air-quality-data" / ".env"
BASE_URL = "https://api.openaq.org/v3"
PM25_PARAMETER_ID = 2  # stable OpenAQ v3 ID for PM2.5


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


def get_api_key():
    load_env_file()
    key = os.environ.get("OPENAQ_API_KEY")
    if not key:
        print(
            json.dumps(
                {
                    "error": "OPENAQ_API_KEY not set. Register at https://openaq.org/register"
                }
            ),
            file=sys.stderr,
        )
        sys.exit(1)
    return key


def api_get(path, params, api_key):
    """Make a GET request to the OpenAQ v3 API. Returns parsed JSON dict."""
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params, safe=",")
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "X-API-Key": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", errors="replace")
        print(json.dumps({"error": f"HTTP {e.code}", "detail": body}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


def fetch_all_pages(path, params, api_key, page_limit=50, delay=0.2):
    """Paginate through all results for a list endpoint."""
    all_results = []
    for page in range(1, page_limit + 1):
        params["page"] = page
        data = api_get(path, params, api_key)
        results = data.get("results", [])
        if not results:
            break
        all_results.extend(results)
        found = data.get("meta", {}).get("found", len(all_results))
        try:
            found = int(found)
        except (TypeError, ValueError):
            found = len(all_results) + 1
        if len(all_results) >= found:
            break
        time.sleep(delay)
    return all_results


def find_pm25_sensors(lat, lon, radius_km, api_key, monitors_only=True):
    """Return list of PM2.5 sensor dicts near a coordinate."""
    data = api_get(
        "/locations",
        {
            "coordinates": f"{lat},{lon}",
            "radius": int(radius_km * 1000),
            "limit": 50,
        },
        api_key,
    )

    sensors = []
    for loc in data.get("results", []):
        if monitors_only and not loc.get("isMonitor", False):
            continue
        for sensor in loc.get("sensors", []):
            if sensor.get("parameter", {}).get("id") == PM25_PARAMETER_ID:
                last = sensor.get("lastUpdated", "")
                sensors.append(
                    {
                        "sensor_id": sensor["id"],
                        "location_id": loc.get("id"),
                        "name": loc.get("name", ""),
                        "provider": loc.get("provider", {}).get("name", ""),
                        "lat": loc.get("coordinates", {}).get("latitude"),
                        "lon": loc.get("coordinates", {}).get("longitude"),
                        "distance_km": round(loc.get("distance", 0) / 1000, 2),
                        "last_updated": last[:10] if isinstance(last, str) else "",
                    }
                )
    # Sort by distance
    sensors.sort(key=lambda s: s["distance_km"])
    return sensors


def fetch_measurements(sensor_id, date_from, date_to, api_key, page_limit=25):
    """Fetch all available measurements for a sensor in the given date range."""
    params = {"limit": 500}
    if date_from:
        params["datetime_from"] = f"{date_from}T00:00:00Z"
    if date_to:
        params["datetime_to"] = f"{date_to}T23:59:59Z"
    return fetch_all_pages(
        f"/sensors/{sensor_id}/measurements", params, api_key, page_limit=page_limit
    )


def hourly_to_daily(measurements, date_from=None, date_to=None):
    """Average hourly readings into daily PM2.5 values.

    Returns dict: {date_str: daily_avg_pm25} filtered to [date_from, date_to] if provided.
    """
    by_day = defaultdict(list)
    for m in measurements:
        v = m.get("value")
        dt = m.get("period", {}).get("datetimeFrom", {})
        d = dt.get("local", dt.get("utc", ""))[:10] if isinstance(dt, dict) else ""
        if v is not None and v >= 0 and len(d) == 10:
            by_day[d].append(float(v))
    daily = {d: sum(vs) / len(vs) for d, vs in by_day.items() if vs}
    if date_from:
        daily = {d: v for d, v in daily.items() if d >= date_from}
    if date_to:
        daily = {d: v for d, v in daily.items() if d <= date_to}
    return daily


def daily_stats(daily_vals):
    """Compute summary statistics from a {date: pm25} dict.

    Returns a dict with mean, days, good/moderate/usg counts, monthly breakdown,
    worst month, and date range.
    """
    if not daily_vals:
        return None
    monthly = defaultdict(list)
    for d, v in daily_vals.items():
        monthly[d[:7]].append(v)

    values = list(daily_vals.values())
    mean = sum(values) / len(values)
    good = sum(1 for v in values if v <= 12)
    mod = sum(1 for v in values if 12 < v <= 35.4)
    usg = sum(1 for v in values if v > 35.4)
    total = len(values)
    worst5 = sorted(values, reverse=True)[:5]
    worst_m = max(monthly, key=lambda k: sum(monthly[k]) / len(monthly[k]))
    wm_avg = sum(monthly[worst_m]) / len(monthly[worst_m])
    wm_max = max(monthly[worst_m])
    all_dates = sorted(daily_vals)

    return {
        "date_range": f"{all_dates[0]} to {all_dates[-1]}",
        "days": total,
        "mean": round(mean, 1),
        "good_days": good,
        "moderate_days": mod,
        "usg_plus_days": usg,
        "good_pct": round(100 * good / total),
        "moderate_pct": round(100 * mod / total),
        "usg_plus_pct": round(100 * usg / total),
        "worst_5_days": [round(v, 1) for v in worst5],
        "worst_month": worst_m,
        "worst_month_avg": round(wm_avg, 1),
        "worst_month_max": round(wm_max, 1),
        "monthly": {
            k: {
                "avg": round(sum(v) / len(v), 1),
                "max": round(max(v), 1),
                "days": len(v),
            }
            for k, v in sorted(monthly.items())
        },
    }


def cmd_sensors(args, api_key):
    sensors = find_pm25_sensors(
        args.lat,
        args.lon,
        args.radius,
        api_key,
        monitors_only=not args.all,
    )
    print(json.dumps({"count": len(sensors), "sensors": sensors}, indent=2))


def cmd_history(args, api_key):
    date_from = args.start_date
    date_to = args.end_date

    if date_from:
        from datetime import datetime, timezone

        _start = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        _end = (
            datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if date_to
            else datetime.now(timezone.utc)
        )
        if (_end - _start).days > 365:
            print(
                json.dumps({"error": "date range cannot exceed 1 year (365 days)"}),
                file=sys.stderr,
            )
            sys.exit(1)

    raw = fetch_measurements(
        args.sensor_id, date_from, date_to, api_key, page_limit=args.page_limit
    )
    daily = hourly_to_daily(raw, date_from=date_from, date_to=date_to)

    output = {
        "sensor_id": args.sensor_id,
        "date_from": date_from,
        "date_to": date_to,
        "raw_measurements": len(raw),
        "daily_values": daily,
    }
    if args.stats:
        stats = daily_stats(daily)
        if stats:
            output["stats"] = stats
    print(json.dumps(output, indent=2))


def main():
    api_key = get_api_key()

    parser = argparse.ArgumentParser(
        description="Fetch PM2.5 data from OpenAQ v3 (official government monitors worldwide)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find PM2.5 monitors near Tokyo
  python fetch_openaq.py sensors --lat 35.685 --lon 139.751 --radius 15

  # Fetch annual history and daily stats for a sensor
  python fetch_openaq.py history --sensor-id 6516560 \\
      --start-date 2024-04-01 --end-date 2025-03-31 --stats

  # Fetch without date filter (all available data)
  python fetch_openaq.py history --sensor-id 6516560

  # Include non-monitor (community) sensors in discovery
  python fetch_openaq.py sensors --lat 35.685 --lon 139.751 --radius 15 --all
""",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ---- sensors subcommand ----
    p_sensors = sub.add_parser("sensors", help="Find PM2.5 monitors near a location")
    p_sensors.add_argument("--lat", type=float, required=True)
    p_sensors.add_argument("--lon", type=float, required=True)
    p_sensors.add_argument(
        "--radius", type=float, default=15, help="Search radius in km (default: 15)"
    )
    p_sensors.add_argument(
        "--all",
        action="store_true",
        help="Include non-monitor community sensors (default: monitors only)",
    )
    p_sensors.set_defaults(func=cmd_sensors)

    # ---- history subcommand ----
    p_hist = sub.add_parser(
        "history", help="Fetch PM2.5 measurement history for a sensor"
    )
    p_hist.add_argument("--sensor-id", type=int, required=True, dest="sensor_id")
    p_hist.add_argument(
        "--start-date", default=None, help="Start date YYYY-MM-DD (default: no filter)"
    )
    p_hist.add_argument(
        "--end-date", default=None, help="End date YYYY-MM-DD (default: no filter)"
    )
    p_hist.add_argument(
        "--stats",
        action="store_true",
        help="Include daily statistics summary in output",
    )
    p_hist.add_argument(
        "--page-limit",
        type=int,
        default=25,
        dest="page_limit",
        help="Max pages to fetch (default: 25 = ~12,500 hourly readings)",
    )
    p_hist.set_defaults(func=cmd_history)

    args = parser.parse_args()
    args.func(args, api_key)


if __name__ == "__main__":
    main()
