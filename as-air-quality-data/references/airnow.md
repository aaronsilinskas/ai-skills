# EPA AirNow API Reference

**Base URL:** `https://www.airnowapi.org/aq/`  
**Registration:** https://docs.airnowapi.org/login  
**Supported regions:** United States, Canada, Mexico

## Full Endpoint Reference

### Current Observations by Zip Code
```
GET /observation/zipCode/current/
  ?format=application/json
  &zipCode={5-digit zip}
  &distance={miles, default 25}
  &API_KEY={key}
```

### Current Observations by Lat/Lng
```
GET /observation/latLong/current/
  ?format=application/json
  &latitude={decimal}
  &longitude={decimal}
  &distance={miles, default 25}
  &API_KEY={key}
```

### Historical Observations by Zip Code
```
GET /observation/zipCode/historical/
  ?format=application/json
  &zipCode={zip}
  &date={YYYY-MM-DDT00-0000}
  &distance={miles}
  &API_KEY={key}
```
Note: The date format is `YYYY-MM-DDT00-0000` (not standard ISO 8601).

### Historical Observations by Lat/Lng
```
GET /observation/latLong/historical/
  ?format=application/json
  &latitude={lat}
  &longitude={lng}
  &date={YYYY-MM-DDT00-0000}
  &distance={miles}
  &API_KEY={key}
```

### Forecast by Zip Code
```
GET /forecast/zipCode/
  ?format=application/json
  &zipCode={zip}
  &date={YYYY-MM-DD}     (optional, defaults to today)
  &distance={miles}
  &API_KEY={key}
```

### Forecast by Lat/Lng
```
GET /forecast/latLong/
  ?format=application/json
  &latitude={lat}
  &longitude={lng}
  &date={YYYY-MM-DD}
  &distance={miles}
  &API_KEY={key}
```

### Observations by Monitoring Site (Bounding Box)
Returns raw monitoring station data rather than reporting area summaries.
```
GET /data/
  ?startDate={YYYY-MM-DDTHH}
  &endDate={YYYY-MM-DDTHH}
  &parameters={comma-separated}
  &BBOX={minLng},{minLat},{maxLng},{maxLat}
  &dataType=C
  &format=application/json
  &verbose=1
  &nowcastonly=0
  &includerawconcentrations=0
  &API_KEY={key}
```
`parameters` values: `PM25`, `PM10`, `OZONE`, `CO`, `SO2`, `NO2`

### Contour Maps (KML)
```
GET /mapcolor/today/gisDec/PM25/   (PM2.5 contour, today)
GET /mapcolor/today/gisDec/Ozone/  (Ozone contour, today)
```
KML format — use with GIS tools or Google Maps.

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `DateObserved` | string | Date as `YYYY-MM-DD` |
| `HourObserved` | int | Hour of observation (24h local time) |
| `LocalTimeZone` | string | Timezone abbreviation (e.g. `PST`, `EST`) |
| `ReportingArea` | string | Named geographic area (city/region) |
| `StateCode` | string | 2-letter state/province code |
| `Latitude` | float | Center of reporting area |
| `Longitude` | float | Center of reporting area |
| `ParameterName` | string | Pollutant name |
| `AQI` | int | US EPA AQI value (-1 if not available) |
| `Category.Number` | int | 1–6 AQI category number |
| `Category.Name` | string | Human-readable category label |

## Notes

- Multiple records returned (one per pollutant) — when displaying a single AQI, take the highest.
- `AQI: -1` means data not available for that hour/location.
- Data is refreshed approximately every hour.
- AirNow data is **not validated** and should not be used for regulatory decisions. For validated data, use EPA AQS (Air Quality System).
- Not useful for real-time data more granular than hourly.
