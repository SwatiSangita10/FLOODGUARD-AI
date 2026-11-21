"""Transparent, preliminary weather-based flood-risk indicator."""
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


PROVIDER_TIMESTAMP_MAX_AGE = timedelta(hours=3)
FETCH_TIMESTAMP_MAX_AGE = timedelta(minutes=15)
FUTURE_TIMESTAMP_TOLERANCE = timedelta(minutes=15)

# Simple heuristic thresholds, not empirically calibrated flood thresholds.
CURRENT_PRECIPITATION_BANDS = (
    (0.1, 0),
    (2, 5),
    (10, 15),
    (math.inf, 25),
)
NEXT_SIX_HOUR_RAINFALL_BANDS = (
    (1, 0),
    (5, 7),
    (20, 18),
    (50, 27),
    (math.inf, 35),
)
NEXT_24_HOUR_RAINFALL_BANDS = (
    (5, 0),
    (20, 8),
    (50, 18),
    (math.inf, 30),
)
PRECIPITATION_PROBABILITY_BANDS = (
    (30, 0),
    (50, 3),
    (70, 6),
    (85, 8),
    (math.inf, 10),
)
RISK_LEVEL_THRESHOLDS = (
    (20, "Low"),
    (40, "Moderate"),
    (70, "High"),
    (101, "Very High"),
)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) and numeric >= 0 else None


def _parse_time(value, zone=None):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone or timezone.utc)
    return parsed.astimezone(timezone.utc)


def _freshness(weather, now):
    location = weather.get("location") or {}
    try:
        zone = ZoneInfo(location.get("timezone", "UTC"))
    except (TypeError, ValueError, KeyError):
        zone = timezone.utc
    current_time = _parse_time((weather.get("current") or {}).get("time"), zone)
    fetched_at = _parse_time(weather.get("fetched_at"))
    if current_time is None or fetched_at is None:
        return {
            "status": "unavailable",
            "provider_timestamp": (weather.get("current") or {}).get("time"),
            "fetched_at": weather.get("fetched_at"),
            "age_minutes": None,
        }, None

    provider_age = now - current_time
    fetch_age = now - fetched_at
    stale = (
        provider_age > PROVIDER_TIMESTAMP_MAX_AGE
        or provider_age < -FUTURE_TIMESTAMP_TOLERANCE
        or fetch_age > FETCH_TIMESTAMP_MAX_AGE
        or fetch_age < -FUTURE_TIMESTAMP_TOLERANCE
    )
    return {
        "status": "stale" if stale else "fresh",
        "provider_timestamp": current_time.isoformat().replace("+00:00", "Z"),
        "fetched_at": fetched_at.isoformat().replace("+00:00", "Z"),
        "age_minutes": max(0, round(provider_age.total_seconds() / 60)),
    }, zone


def _band_points(value, bands):
    for upper_bound, points in bands:
        if value < upper_bound:
            return points
    return bands[-1][1]


def _hourly_measurements(weather, zone, now, hours):
    hourly = weather.get("hourly") or {}
    times = hourly.get("time") or []
    values = (hourly.get("values") or {}).get("precipitation") or []
    probabilities = (hourly.get("values") or {}).get("precipitation_probability") or []
    if not isinstance(times, list) or not isinstance(values, list):
        return [], []

    rain = []
    probability_values = []
    end = now + timedelta(hours=hours)
    for index, timestamp in enumerate(times):
        timestamp_utc = _parse_time(timestamp, zone)
        if timestamp_utc is None or not now <= timestamp_utc < end:
            continue
        amount = _number(values[index]) if index < len(values) else None
        if amount is not None:
            rain.append(amount)
        probability = _number(probabilities[index]) if index < len(probabilities) else None
        if probability is not None and probability <= 100:
            probability_values.append(probability)
    return rain, probability_values


def _factor(key, label, value, unit, points, maximum, explanation):
    return {
        "key": key,
        "label": label,
        "value": round(value, 2),
        "unit": unit,
        "points": points,
        "maximum_points": maximum,
        "explanation": explanation,
    }


def _risk_level(score):
    for upper_bound, level in RISK_LEVEL_THRESHOLDS:
        if score < upper_bound:
            return level
    return "Very High"


def assess_weather(weather, *, location_name=None, assessed_at=None):
    """Score only present, non-negative weather measurements; omit missing inputs."""
    now = assessed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    location = weather.get("location") or {}
    current = weather.get("current") or {}
    current_values = current.get("values") or {}
    freshness, zone = _freshness(weather, now)
    factors = []

    if freshness["status"] == "fresh":
        current_rain = _number(current_values.get("precipitation"))
        if current_rain is not None:
            points = _band_points(current_rain, CURRENT_PRECIPITATION_BANDS)
            factors.append(_factor(
                "current_precipitation",
                "Current precipitation",
                current_rain,
                "mm",
                points,
                25,
                f"{current_rain:g} mm currently; this contributes {points} of 25 points.",
            ))

        six_hour_rain, _ = _hourly_measurements(weather, zone, now, 6)
        if six_hour_rain:
            amount = sum(six_hour_rain)
            points = _band_points(amount, NEXT_SIX_HOUR_RAINFALL_BANDS)
            factors.append(_factor(
                "next_6_hour_precipitation",
                "Forecast precipitation · next 6 hours",
                amount,
                "mm",
                points,
                35,
                f"{amount:g} mm forecast in available hourly values; this contributes {points} of 35 points.",
            ))

        day_rain, probabilities = _hourly_measurements(weather, zone, now, 24)
        if day_rain:
            amount = sum(day_rain)
            points = _band_points(amount, NEXT_24_HOUR_RAINFALL_BANDS)
            factors.append(_factor(
                "next_24_hour_precipitation",
                "Forecast precipitation · next 24 hours",
                amount,
                "mm",
                points,
                30,
                f"{amount:g} mm forecast in available hourly values; this contributes {points} of 30 points.",
            ))
        if probabilities:
            probability = max(probabilities)
            points = _band_points(probability, PRECIPITATION_PROBABILITY_BANDS)
            factors.append(_factor(
                "precipitation_probability",
                "Maximum precipitation probability · next 24 hours",
                probability,
                "%",
                points,
                10,
                f"Maximum available hourly probability is {probability:g}%; this contributes {points} of 10 points.",
            ))

    completeness = "complete" if len(factors) == 4 else "partial" if factors else "unavailable"
    score = None
    level = None
    if freshness["status"] == "fresh" and factors:
        earned = sum(factor["points"] for factor in factors)
        possible = sum(factor["maximum_points"] for factor in factors)
        score = round(earned / possible * 100)
        level = _risk_level(score)

    if freshness["status"] == "stale":
        explanation = "No risk level is shown because the weather data is stale."
    elif not factors:
        explanation = "No risk level is shown because usable precipitation measurements are unavailable."
    else:
        drivers = [factor["label"].lower() for factor in factors if factor["points"] > 0]
        driver_text = ", ".join(drivers) if drivers else "the available precipitation measurements are low"
        explanation = (
            f"The preliminary indicator is {level} ({score}/100) based on {driver_text}. "
            "The score is normalized across available factors only; unavailable inputs are excluded."
        )

    return {
        "assessment_status": (
            "available" if score is not None
            else "stale" if freshness["status"] == "stale"
            else "unavailable"
        ),
        "risk_level": level,
        "score": score,
        "location": {
            "name": location_name or location.get("name") or "Selected location",
            "latitude": location.get("requested_latitude", location.get("latitude")),
            "longitude": location.get("requested_longitude", location.get("longitude")),
        },
        "assessed_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "weather_freshness": freshness,
        "data_completeness": completeness,
        "provider": weather.get("source") or {"name": "Unknown"},
        "factors": factors,
        "explanation": explanation,
        "limitations": (
            "Preliminary weather-based indicator only; thresholds are heuristic, not scientifically "
            "validated flood thresholds. Weather alone cannot establish flooding or predict local impacts."
        ),
    }
