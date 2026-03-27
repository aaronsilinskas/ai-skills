#!/usr/bin/env python3
"""Fetch air quality data from the IQAir (AirVisual) API v2.

Reads IQAIR_API_KEY from the environment or ~/.config/as-air-quality-data/.env.
Outputs JSON to stdout.
"""

import argparse
import json
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

BASE_URL = "https://api.airvisual.com/v2"

IQAIR_ERRORS = {
    "call_limit_reached": "Daily API call limit reached",
    "api_key_expired": "API key has expired",
    "incorrect_api_key": "Invalid API key",
    "ip_location_failed": "Could not determine location from IP address",
    "no_nearest_station": "No monitoring station found near the requested location",
    "feature_not_available": "This endpoint is not available on your plan",
    "too_many_requests": "Too many requests — rate limit exceeded",
    "permission_denied": "Your API key does not have permission for this request",
    "city_not_found": "City not found",
    "state_not_found": "State not found",
    "country_not_found": "Country not found",
}


def fetch(endpoint, extra_params, api_key):
    url = f"{BASE_URL}/{endpoint}"
    params = {"key": api_key}
    params.update(extra_params)
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        body = resp.json()
    except requests.exceptions.HTTPError as e:
        print(
            json.dumps({"error": str(e), "status_code": resp.status_code}),
            file=sys.stderr,
        )
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

    status = body.get("status")
    if status != "success":
        msg = IQAIR_ERRORS.get(status, f"API error: {status}")
        print(json.dumps({"error": msg, "status": status}), file=sys.stderr)
        sys.exit(1)

    return body.get("data")


def main():
    load_env_file()
    api_key = os.environ.get("IQAIR_API_KEY")
    if not api_key:
        print(
            json.dumps({"error": "IQAIR_API_KEY environment variable not set"}),
            file=sys.stderr,
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Fetch air quality data from IQAir")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--nearest",
        action="store_true",
        help="Return nearest station to your IP address location",
    )
    mode.add_argument(
        "--city",
        help="City name (use with --state and --country)",
    )
    mode.add_argument(
        "--list-states",
        metavar="COUNTRY",
        help="List supported states for a country",
    )
    mode.add_argument(
        "--list-cities",
        nargs=2,
        metavar=("STATE", "COUNTRY"),
        help="List supported cities for a state/country pair",
    )
    parser.add_argument("--state", help="State name (use with --city)")
    parser.add_argument("--country", help="Country name (use with --city)")
    args = parser.parse_args()

    if args.city and (not args.state or not args.country):
        parser.error("--city requires both --state and --country")

    if args.nearest:
        data = fetch("nearest_city", {}, api_key)
    elif args.city:
        data = fetch(
            "city",
            {"city": args.city, "state": args.state, "country": args.country},
            api_key,
        )
    elif args.list_states:
        data = fetch("states", {"country": args.list_states}, api_key)
    else:  # --list-cities
        state, country = args.list_cities
        data = fetch("cities", {"state": state, "country": country}, api_key)

    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
