"""
Analyze PurpleAir history JSON files produced by fetch_purpleair.py --history.

Usage:
    python scripts/analyze_history.py file1.json [file2.json ...]
    python scripts/analyze_history.py /tmp/pgh_*.json

Each file must be either:
  - A single-sensor history object: {"sensor_index": N, "history": [{...}, ...]}
  - A list of daily readings:       [{...}, ...]

Each reading is expected to have "pm2.5_cf_1_corrected" (EPA-corrected PM2.5) and
"time_stamp" (Unix seconds) fields. Readings with null or negative values are excluded.

Output per file:
  - Monthly breakdown: avg and max PM2.5 (µg/m³) per month, sorted worst-first then full table
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


def analyze(path: Path) -> None:
    with open(path) as f:
        data = json.load(f)

    rows = data.get("history", data) if isinstance(data, dict) else data
    valid_rows = [
        r
        for r in rows
        if r.get("pm2.5_cf_1_corrected") is not None
        and r["pm2.5_cf_1_corrected"] >= 0
        and r.get("time_stamp") is not None
    ]

    label = path.stem
    if not valid_rows:
        print(f"\n{label}: No valid readings")
        return

    readings = [r["pm2.5_cf_1_corrected"] for r in valid_rows]
    n = len(readings)
    avg = sum(readings) / n
    good = sum(1 for x in readings if x <= GOOD_MAX)
    moderate = sum(1 for x in readings if GOOD_MAX < x <= MODERATE_MAX)
    usg = sum(1 for x in readings if x > MODERATE_MAX)
    top5 = sorted(readings, reverse=True)[:5]

    # Monthly grouping
    by_month: dict[str, list[float]] = defaultdict(list)
    for r in valid_rows:
        dt = datetime.fromtimestamp(r["time_stamp"], tz=timezone.utc)
        key = dt.strftime("%b %Y")
        by_month[key].append(r["pm2.5_cf_1_corrected"])

    monthly = [
        (month, sum(vals) / len(vals), max(vals)) for month, vals in by_month.items()
    ]
    # Sort chronologically for the full table
    monthly_chrono = sorted(monthly, key=lambda x: datetime.strptime(x[0], "%b %Y"))
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
