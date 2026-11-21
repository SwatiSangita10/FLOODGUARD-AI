"""Open-Meteo forecast and geocoding client."""
import json
import math
import socket
from datetime import date, datetime, timezone
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
SOURCE_NAME = "Open-Meteo"
REQUEST_TIMEOUT_SECONDS = 8

CURRENT_VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "weather_code",
    "wind_speed_10m",
    "pressure_msl",
    "cloud_cover",
)
HOURLY_VARIABLES = (
    "temperature_2m",
    "precipitation",
    "precipitation_probability",
    "relative_humidity_2m",
    "wind_speed_10m",
)
DAILY_VARIABLES = (
    "precipitation_sum",
    "rain_sum",
    "precipitation_probability_max",
    "temperature_2m_max",
    "temperature_2m_min",
    "weather_code",
)


class WeatherProviderError(Exception):
    """Raised when Open-Meteo cannot return a valid response."""


def _request_json(base_url, params):
    request = Request(
        f"{base_url}?{urlencode(params)}",
        headers={"Accept": "application/json", "User-Agent": "FloodGuardAI/1.0"},
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, socket.timeout, OSError, HTTPException, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WeatherProviderError from exc
    if not isinstance(payload, dict) or payload.get("error"):
        raise WeatherProviderError
    return payload


def _validate_weather_payload(payload):
    for section, variables in (
        ("current", CURRENT_VARIABLES),
        ("current_units", CURRENT_VARIABLES),
        ("hourly", HOURLY_VARIABLES),
        ("hourly_units", HOURLY_VARIABLES),
        ("daily", DAILY_VARIABLES),
        ("daily_units", DAILY_VARIABLES),
    ):
        data = payload.get(section)
        if not isinstance(data, dict) or any(variable not in data for variable in variables):
            raise WeatherProviderError
    hourly = payload["hourly"]
    daily = payload["daily"]
    if not isinstance(hourly.get("time"), list) or not isinstance(daily.get("time"), list):
        raise WeatherProviderError
    for variable in HOURLY_VARIABLES:
        if not isinstance(hourly[variable], list) or len(hourly[variable]) != len(hourly["time"]):
            raise WeatherProviderError
        if any(value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)) for value in hourly[variable]):
            raise WeatherProviderError
    for variable in DAILY_VARIABLES:
        if not isinstance(daily[variable], list) or len(daily[variable]) != len(daily["time"]):
            raise WeatherProviderError
        if any(value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)) for value in daily[variable]):
            raise WeatherProviderError
    if not isinstance(payload.get("timezone"), str) or not payload["timezone"]:
        raise WeatherProviderError
    for coordinate, lower, upper in (("latitude", -90, 90), ("longitude", -180, 180)):
        value = payload.get(coordinate)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
            raise WeatherProviderError
    try:
        ZoneInfo(payload["timezone"])
    except (ZoneInfoNotFoundError, ValueError):
        raise WeatherProviderError
    current = payload["current"]
    if not isinstance(current.get("time"), str) or not current["time"]:
        raise WeatherProviderError
    try:
        datetime.fromisoformat(current["time"])
        for value in hourly["time"]:
            datetime.fromisoformat(value)
        for value in daily["time"]:
            date.fromisoformat(value)
    except ValueError as exc:
        raise WeatherProviderError from exc
    for variable in CURRENT_VARIABLES:
        value = current[variable]
        if not isinstance(payload["current_units"][variable], str):
            raise WeatherProviderError
        if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
            raise WeatherProviderError
    if any(not isinstance(value, str) for value in hourly["time"] + daily["time"]):
        raise WeatherProviderError
    for section, variables in (("hourly_units", HOURLY_VARIABLES), ("daily_units", DAILY_VARIABLES)):
        if any(not isinstance(payload[section][variable], str) for variable in variables):
            raise WeatherProviderError


def fetch_weather(latitude, longitude, *, timezone_name=None):
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join(CURRENT_VARIABLES),
        "hourly": ",".join(HOURLY_VARIABLES),
        "daily": ",".join(DAILY_VARIABLES),
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
        "wind_speed_unit": "kmh",
        "forecast_hours": 24,
        "forecast_days": 7,
        "timezone": timezone_name or "auto",
    }
    payload = _request_json(WEATHER_URL, params)
    _validate_weather_payload(payload)
    return {
        "location": {
            "latitude": payload.get("latitude", latitude),
            "longitude": payload.get("longitude", longitude),
            "requested_latitude": latitude,
            "requested_longitude": longitude,
            "timezone": payload["timezone"],
            "timezone_abbreviation": payload.get("timezone_abbreviation"),
            "elevation": payload.get("elevation"),
        },
        "current": {
            "time": payload["current"].get("time"),
            "interval_seconds": payload["current"].get("interval"),
            "values": {key: payload["current"][key] for key in CURRENT_VARIABLES},
            "units": {key: payload["current_units"][key] for key in CURRENT_VARIABLES},
            "interpretation": "Current conditions are based on weather model data and may not represent ground-station observations.",
        },
        "hourly": {
            "time": payload["hourly"]["time"],
            "values": {key: payload["hourly"][key] for key in HOURLY_VARIABLES},
            "units": {key: payload["hourly_units"][key] for key in HOURLY_VARIABLES},
            "type": "forecast",
        },
        "daily": {
            "time": payload["daily"]["time"],
            "values": {key: payload["daily"][key] for key in DAILY_VARIABLES},
            "units": {key: payload["daily_units"][key] for key in DAILY_VARIABLES},
            "type": "forecast",
        },
        "source": {
            "name": SOURCE_NAME,
            "attribution_url": "https://open-meteo.com/",
        },
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def search_locations(query, *, limit=8):
    payload = _request_json(
        GEOCODING_URL,
        {"name": query, "count": limit, "language": "en", "format": "json"},
    )
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise WeatherProviderError

    locations = []
    for item in results[:limit]:
        if not isinstance(item, dict):
            raise WeatherProviderError
        try:
            latitude = float(item["latitude"])
            longitude = float(item["longitude"])
            name = item["name"].strip()
            country = item["country"].strip()
        except (AttributeError, KeyError, TypeError, ValueError):
            raise WeatherProviderError
        if (
            not isinstance(name, str)
            or not isinstance(country, str)
            or not name
            or not country
            or not math.isfinite(latitude)
            or not math.isfinite(longitude)
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            raise WeatherProviderError
        timezone_name = item.get("timezone")
        if timezone_name is not None:
            try:
                ZoneInfo(timezone_name)
            except (TypeError, ZoneInfoNotFoundError, ValueError):
                raise WeatherProviderError
        admin1 = item.get("admin1")
        country_code = item.get("country_code")
        locations.append({
            "name": name,
            "admin1": admin1 if isinstance(admin1, str) else None,
            "country": country,
            "country_code": country_code if isinstance(country_code, str) else None,
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone_name,
        })
    return locations
