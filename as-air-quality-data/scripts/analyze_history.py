"""
Analyze PurpleAir history JSON files produced by fetch_purpleair.py --history.

Usage:
    python scripts/analyze_history.py file1.json [file2.json ...]
    python scripts/analyze_history.py /tmp/pgh_*.json

Each file must be either:
  - A single-sensor history object: {"sensor_index": N, "history": [{...}, ...]}
  - A list of daily readings:       [{...}, ...]

Each reading is expected to have a "pm2.5_cf_1_corrected" field (EPA-corrected PM2.5).
Readings with null or negative values are excluded.

Output per file:
  - Number of valid days
  - Annual mean PM2.5 (µg/m³)
  - Day counts and percentages for Good / Moderate / USG+ categories
  - 5 worst daily values
"""

import json
import sys
from pathlib import Path

# EPA PM2.5 breakpoints (µg/m³, 24-hr average)
GOOD_MAX = 12.0
MODERATE_MAX = 35.4


def analyze(path: Path) -> None:
    with open(path) as f:
        data = json.load(f)

    rows = data.get("history", data) if isinstance(data, dict) else data
    readings = [
        r["pm2.5_cf_1_corrected"]
        for r in rows
        if r.get("pm2.5_cf_1_corrected") is not None and r["pm2.5_cf_1_corrected"] >= 0
    ]

    label = path.stem
    if not readings:
        print(f"\n{label}: No valid readings")
        return

    n = len(readings)
    avg = sum(readings) / n
    good = sum(1 for x in readings if x <= GOOD_MAX)
    moderate = sum(1 for x in readings if GOOD_MAX < x <= MODERATE_MAX)
    usg = sum(1 for x in readings if x > MODERATE_MAX)
    top5 = sorted(readings, reverse=True)[:5]

    print(f"\n{label}")
    print(f"  Days: {n}  |  Mean PM2.5: {avg:.1f} µg/m³")
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
