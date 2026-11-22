"""Open-Meteo forecast and geocoding client."""
import json
import logging
import math
import os
import socket
import time
from datetime import date, datetime, timezone
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


logger = logging.getLogger(__name__)

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
# Used instead of the free endpoints only when OPEN_METEO_API_KEY is configured.
COMMERCIAL_WEATHER_URL = "https://customer-api.open-meteo.com/v1/forecast"
COMMERCIAL_GEOCODING_URL = "https://customer-geocoding-api.open-meteo.com/v1/search"
REQUEST_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 0.7
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
    """Raised when Open-Meteo cannot return a valid response.

    ``reason`` is a short diagnostic code (never a secret) that is logged and
    returned to the client so the real cause is visible in production.
    """

    def __init__(self, reason="provider_error"):
        super().__init__(reason)
        self.reason = reason


def _request_json(base_url, params):
    api_key = os.environ.get("OPEN_METEO_API_KEY", "").strip()
    if api_key:
        base_url = {
            WEATHER_URL: COMMERCIAL_WEATHER_URL,
            GEOCODING_URL: COMMERCIAL_GEOCODING_URL,
        }.get(base_url, base_url)
        params = {**params, "apikey": api_key}

    request = Request(
        f"{base_url}?{urlencode(params)}",
        headers={"Accept": "application/json", "User-Agent": "FloodGuardAI/1.0"},
    )
    last_reason = "provider_error"
    for attempt in range(1, REQUEST_ATTEMPTS + 1):
        retryable = True
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            last_reason = f"http_{exc.code}"
            # 429 means Open-Meteo is rate limiting this server's IP address.
            retryable = exc.code >= 500
            logger.warning("Open-Meteo returned HTTP %s for %s", exc.code, base_url)
        except (URLError, TimeoutError, socket.timeout, OSError, HTTPException) as exc:
            last_reason = "network_error"
            logger.warning("Open-Meteo request failed (%s) for %s", type(exc).__name__, base_url)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            last_reason = "invalid_json"
            retryable = False
            logger.warning("Open-Meteo returned a non-JSON body (%s) for %s", type(exc).__name__, base_url)
        else:
            if not isinstance(payload, dict):
                logger.warning("Open-Meteo returned a non-object JSON body for %s", base_url)
                raise WeatherProviderError("invalid_payload:not_an_object")
            if payload.get("error"):
                logger.warning("Open-Meteo reported an error: %s", str(payload.get("reason"))[:200])
                raise WeatherProviderError("provider_rejected_request")
            return payload
        if not retryable or attempt == REQUEST_ATTEMPTS:
            break
        time.sleep(RETRY_DELAY_SECONDS)
    raise WeatherProviderError(last_reason)


def _invalid(detail):
    logger.warning("Open-Meteo response failed validation: %s", detail)
    return WeatherProviderError(f"invalid_payload:{detail}")


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


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
        if not isinstance(data, dict):
            raise _invalid(f"missing section {section}")
        missing = [variable for variable in variables if variable not in data]
        if missing:
            raise _invalid(f"{section} lacks {','.join(missing)}")
    hourly = payload["hourly"]
    daily = payload["daily"]
    if not isinstance(hourly.get("time"), list) or not isinstance(daily.get("time"), list):
        raise _invalid("hourly/daily time is not a list")
    for section_name, section, variables in (
        ("hourly", hourly, HOURLY_VARIABLES),
        ("daily", daily, DAILY_VARIABLES),
    ):
        for variable in variables:
            values = section[variable]
            if not isinstance(values, list) or len(values) != len(section["time"]):
                raise _invalid(f"{section_name}.{variable} length differs from time")
            if any(value is not None and not _is_number(value) for value in values):
                raise _invalid(f"{section_name}.{variable} has non-numeric values")
    if not isinstance(payload.get("timezone"), str) or not payload["timezone"]:
        raise _invalid("timezone missing")
    for coordinate, lower, upper in (("latitude", -90, 90), ("longitude", -180, 180)):
        value = payload.get(coordinate)
        if not _is_number(value) or not lower <= value <= upper:
            raise _invalid(f"{coordinate} missing or out of range")
    try:
        ZoneInfo(payload["timezone"])
    except (ZoneInfoNotFoundError, ValueError):
        raise _invalid(f"timezone {payload['timezone']!r} not found; install the tzdata package")
    current = payload["current"]
    if not isinstance(current.get("time"), str) or not current["time"]:
        raise _invalid("current.time missing")
    try:
        datetime.fromisoformat(current["time"])
        for value in hourly["time"]:
            datetime.fromisoformat(value)
        for value in daily["time"]:
            date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise _invalid("unparseable time value") from exc
    for variable in CURRENT_VARIABLES:
        value = current[variable]
        if not isinstance(payload["current_units"][variable], str):
            raise _invalid(f"current_units.{variable} is not text")
        if value is not None and not _is_number(value):
            raise _invalid(f"current.{variable} is not numeric")
    for section, variables in (("hourly_units", HOURLY_VARIABLES), ("daily_units", DAILY_VARIABLES)):
        if any(not isinstance(payload[section][variable], str) for variable in variables):
            raise _invalid(f"{section} contains non-text units")


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
