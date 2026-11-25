#!/usr/bin/env python3
"""Fetch air quality data from the EPA AirNow API.

Reads AIRNOW_API_KEY from the environment or ~/.config/as-air-quality-data/.env.
Outputs JSON to stdout.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests

BASE_URL = "https://www.airnowapi.org/aq"
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


def build_params(api_key, extra):
    params = {"format": "application/json", "API_KEY": api_key}
    params.update(extra)
    return params


def fetch(path, params):
    url = f"{BASE_URL}/{path}/"
    try:
        resp = requests.get(url, params=params, timeout=15)
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


def main():
    load_env_file()
    api_key = os.environ.get("AIRNOW_API_KEY")
    if not api_key:
        print(
            json.dumps({"error": "AIRNOW_API_KEY environment variable not set"}),
            file=sys.stderr,
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Fetch AQI data from EPA AirNow")
    location = parser.add_mutually_exclusive_group(required=True)
    location.add_argument("--zip", help="5-digit US zip code")
    location.add_argument("--lat", type=float, help="Latitude (use with --lng)")
    parser.add_argument("--lng", type=float, help="Longitude (use with --lat)")
    parser.add_argument(
        "--mode",
        choices=["current", "forecast", "historical"],
        default="current",
        help="Data mode (default: current)",
    )
    parser.add_argument(
        "--date",
        help="Date for forecast or historical (YYYY-MM-DD). Required for historical.",
    )
    parser.add_argument(
        "--distance",
        type=int,
        default=25,
        help="Search radius in miles (default: 25)",
    )
    args = parser.parse_args()

    if args.lat is not None and args.lng is None:
        parser.error("--lng is required when using --lat")

    if args.mode == "historical" and not args.date:
        parser.error("--date is required for historical mode")

    extra = {"distance": args.distance}

    if args.zip:
        if args.mode == "current":
            path = "observation/zipCode/current"
            extra["zipCode"] = args.zip
        elif args.mode == "forecast":
            path = "forecast/zipCode"
            extra["zipCode"] = args.zip
            if args.date:
                extra["date"] = args.date
        else:  # historical
            path = "observation/zipCode/historical"
            extra["zipCode"] = args.zip
            extra["date"] = f"{args.date}T00-0000"
    else:
        if args.mode == "current":
            path = "observation/latLong/current"
            extra["latitude"] = args.lat
            extra["longitude"] = args.lng
        elif args.mode == "forecast":
            path = "forecast/latLong"
            extra["latitude"] = args.lat
            extra["longitude"] = args.lng
            if args.date:
                extra["date"] = args.date
        else:  # historical
            path = "observation/latLong/historical"
            extra["latitude"] = args.lat
            extra["longitude"] = args.lng
            extra["date"] = f"{args.date}T00-0000"

    data = fetch(path, build_params(api_key, extra))
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
