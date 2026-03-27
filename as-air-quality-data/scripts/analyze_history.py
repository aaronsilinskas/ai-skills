"""
Analyze PM2.5 history JSON files from fetch_purpleair.py or fetch_openaq.py.

Usage:
    python scripts/analyze_history.py file1.json [file2.json ...]
    python scripts/analyze_history.py /tmp/sensors_*.json

Accepted formats
----------------
PurpleAir  — {"sensor_index": N, "history": [{time_stamp, pm2.5_cf_1_corrected, ...}]}
             or a bare list of those dicts
OpenAQ     — {"sensor_id": N, "daily_values": {"YYYY-MM-DD": float, ...}}
             (produced by fetch_openaq.py history)

Output per file:
  - Worst month (shown first)
  - Monthly table: avg and max PM2.5 (µg/m³)
  - Annual summary: mean PM2.5, day counts/percentages for Good / Moderate / USG+ categories
  - 5 worst daily values
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# EPA PM2.5 breakpoints (µg/m³, 24-hr average)
GOOD_MAX = 12.0
MODERATE_MAX = 35.4


def load_daily_values(data) -> dict:
    """Return {YYYY-MM-DD: pm25_float} from either PurpleAir or OpenAQ format."""
    # OpenAQ format: {"sensor_id": N, "daily_values": {"YYYY-MM-DD": float}}
    if isinstance(data, dict) and "daily_values" in data:
        return {
            k: float(v)
            for k, v in data["daily_values"].items()
            if v is not None and float(v) >= 0
        }
    # PurpleAir format: {"sensor_index": N, "history": [...]} or bare list
    rows = data.get("history", data) if isinstance(data, dict) else data
    daily = {}
    for r in rows:
        pm25 = r.get("pm2.5_cf_1_corrected")
        ts = r.get("time_stamp")
        if pm25 is None or pm25 < 0 or ts is None:
            continue
        date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        daily[date] = pm25
    return daily


def analyze(path: Path) -> None:
    with open(path) as f:
        data = json.load(f)

    daily = load_daily_values(data)
    label = path.stem
    if not daily:
        print(f"\n{label}: No valid readings")
        return

    values = list(daily.values())
    n = len(values)
    avg = sum(values) / n
    good = sum(1 for x in values if x <= GOOD_MAX)
    moderate = sum(1 for x in values if GOOD_MAX < x <= MODERATE_MAX)
    usg = sum(1 for x in values if x > MODERATE_MAX)
    top5 = sorted(values, reverse=True)[:5]

    by_month: dict[str, list] = defaultdict(list)
    for date, pm25 in daily.items():
        key = datetime.strptime(date, "%Y-%m-%d").strftime("%b %Y")
        by_month[key].append(pm25)

    monthly_chrono = sorted(
        [(m, sum(v) / len(v), max(v)) for m, v in by_month.items()],
        key=lambda x: datetime.strptime(x[0], "%b %Y"),
    )
    worst_month = max(monthly_chrono, key=lambda x: x[1])

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(
        f"  Worst month: {worst_month[0]} — avg {worst_month[1]:.1f} µg/m³, max {worst_month[2]:.1f} µg/m³\n"
    )
    print(f"  {'Month':<12}  {'Avg PM2.5':>10}  {'Max PM2.5':>10}")
    print(f"  {'-'*12}  {'-'*10}  {'-'*10}")
    for month, mavg, mmax in monthly_chrono:
        print(f"  {month:<12}  {mavg:>9.1f}  {mmax:>9.1f}")
    print()
    print(f"  Annual mean: {avg:.1f} µg/m³  |  Days: {n}")
    print(
        f"  Good (≤12): {good}d ({100*good//n}%)"
        f"  Moderate (12–35): {moderate}d ({100*moderate//n}%)"
        f"  USG+ (>35): {usg}d ({100*usg//n}%)"
    )
    print(f"  5 worst days (µg/m³): {[round(x, 1) for x in top5]}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/analyze_history.py file1.json [file2.json ...]")
        sys.exit(1)

    for arg in sys.argv[1:]:
        for path in sorted(Path(".").glob(arg)) if "*" in arg else [Path(arg)]:
            analyze(path)


if __name__ == "__main__":
    main()
