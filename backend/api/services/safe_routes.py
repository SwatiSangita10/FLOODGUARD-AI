"""OSRM route retrieval and cautious assessment using available project data."""
import json
import math
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from pymongo.errors import PyMongoError

from api.services.reports import (
    ReportDatabaseUnavailable,
    list_flood_reports_near_route,
)
from api.services.sachet_feed import (
    SachetFeedDatabaseUnavailable,
    get_sachet_feed,
)
from api.services.risk_assessment import assess_weather
from api.services.weather import WeatherProviderError, fetch_weather
from database.mongodb import (
    MongoDBConfigurationError,
    check_mongodb_and_prepare_schema,
)


ROUTING_URL = "https://router.project-osrm.org/route/v1/driving"
ROUTING_SOURCE = "OSRM public routing service"
ROUTE_CORRIDOR_METERS = 500
MAX_ROUTE_ALTERNATIVES = 2
MAX_WEATHER_SAMPLES = 3


class RouteProviderError(Exception):
    """Raised when OSRM cannot provide a valid driving route."""


class RouteStorageError(Exception):
    """Raised when the route assessment history cannot be stored."""


def _request_routing_json(url):
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "FloodGuardAI/1.0"},
    )
    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (
        HTTPError,
        URLError,
        TimeoutError,
        socket.timeout,
        OSError,
        HTTPException,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise RouteProviderError from exc
    if not isinstance(payload, dict) or payload.get("code") != "Ok":
        raise RouteProviderError
    return payload


def _valid_coordinate(pair):
    if not isinstance(pair, list) or len(pair) != 2:
        return False
    longitude, latitude = pair
    return (
        isinstance(latitude, (int, float))
        and not isinstance(latitude, bool)
        and math.isfinite(latitude)
        and -90 <= latitude <= 90
        and isinstance(longitude, (int, float))
        and not isinstance(longitude, bool)
        and math.isfinite(longitude)
        and -180 <= longitude <= 180
    )


def _normalize_route(route):
    if not isinstance(route, dict):
        raise RouteProviderError
    distance = route.get("distance")
    duration = route.get("duration")
    geometry = route.get("geometry")
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if (
        isinstance(distance, bool)
        or not isinstance(distance, (int, float))
        or not math.isfinite(distance)
        or distance < 0
        or isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration < 0
        or not isinstance(coordinates, list)
        or len(coordinates) < 2
        or any(not _valid_coordinate(pair) for pair in coordinates)
    ):
        raise RouteProviderError
    return {
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "distance_m": round(distance, 1),
        "duration_s": round(duration, 1),
    }


def get_driving_routes(origin, destination):
    """Return real OSRM geometry, metrics, and any provider-supplied alternatives."""
    origin_pair = [origin["longitude"], origin["latitude"]]
    destination_pair = [destination["longitude"], destination["latitude"]]
    coordinates = ";".join(
        f"{longitude:.6f},{latitude:.6f}"
        for longitude, latitude in (origin_pair, destination_pair)
    )
    payload = _request_routing_json(
        f"{ROUTING_URL}/{coordinates}?alternatives=true&overview=full&geometries=geojson&steps=false"
    )
    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes:
        raise RouteProviderError
    primary = _normalize_route(routes[0])
    alternatives = [
        _normalize_route(route)
        for route in routes[1 : MAX_ROUTE_ALTERNATIVES + 1]
    ]
    return primary, alternatives


def _sample_route_points(coordinates):
    indices = sorted({
        0,
        len(coordinates) // 2,
        len(coordinates) - 1,
    })
    return [
        {"longitude": coordinates[index][0], "latitude": coordinates[index][1]}
        for index in indices[:MAX_WEATHER_SAMPLES]
    ]


def _distance_to_segment_meters(point, start, end):
    """Approximate point-to-segment distance in a local tangent plane."""
    latitude_scale = math.cos(math.radians(point["latitude"]))
    point_x = math.radians(point["longitude"]) * latitude_scale
    point_y = math.radians(point["latitude"])

    def project(coordinate):
        return (
            math.radians(coordinate[0]) * latitude_scale,
            math.radians(coordinate[1]),
        )

    start_x, start_y = project(start)
    end_x, end_y = project(end)
    delta_x = end_x - start_x
    delta_y = end_y - start_y
    segment_length_squared = delta_x * delta_x + delta_y * delta_y
    if segment_length_squared == 0:
        fraction = 0
    else:
        fraction = max(
            0,
            min(
                1,
                ((point_x - start_x) * delta_x + (point_y - start_y) * delta_y)
                / segment_length_squared,
            ),
        )
    nearest_x = start_x + fraction * delta_x
    nearest_y = start_y + fraction * delta_y
    return math.hypot(point_x - nearest_x, point_y - nearest_y) * 6_371_000


def _report_distance_from_route(report, coordinates):
    point = {"latitude": report["latitude"], "longitude": report["longitude"]}
    return min(
        _distance_to_segment_meters(point, start, end)
        for start, end in zip(coordinates, coordinates[1:])
    )


def _reports_near_route(coordinates):
    observations = []
    missing_coordinates = 0
    checked = 0
    unavailable = False
    for status in ("verified", "pending"):
        try:
            page = list_flood_reports_near_route(coordinates, status=status, limit=500)
        except ReportDatabaseUnavailable:
            unavailable = True
            continue
        checked += page["count"]
        missing_coordinates += page["without_coordinates"]
        for report in page["results"]:
            try:
                distance = _report_distance_from_route(report, coordinates)
            except (KeyError, TypeError, ValueError):
                continue
            if distance <= ROUTE_CORRIDOR_METERS:
                created_at = report.get("created_at")
                observations.append({
                    "report_id": str(report.get("_id") or report.get("report_id") or ""),
                    "location_name": report.get("location_name"),
                    "latitude": float(report["latitude"]),
                    "longitude": float(report["longitude"]),
                    "severity": report.get("severity"),
                    "description": report.get("description"),
                    "verification_status": status,
                    "created_at": (
                        created_at.isoformat()
                        if isinstance(created_at, datetime)
                        else None
                    ),
                    "distance_from_route_m": round(distance),
                    "source_label": "Citizen-submitted flood report",
                })
    if unavailable:
        state = "unavailable"
    elif observations:
        state = "available"
    elif missing_coordinates:
        state = "insufficient_location_data"
    else:
        state = "none"
    return {
        "status": state,
        "reports_checked": checked,
        "reports_without_coordinates": missing_coordinates,
        "observations": observations,
    }


def _valid_coordinate_values(latitude, longitude):
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return latitude, longitude


def _explicit_alert_coordinates(alert):
    location = alert.get("location")
    if isinstance(location, dict) and location.get("type") == "Point":
        coordinates = location.get("coordinates")
        if isinstance(coordinates, list) and len(coordinates) == 2:
            result = _valid_coordinate_values(coordinates[1], coordinates[0])
            if result:
                return result
    for latitude_key, longitude_key in (
        ("latitude", "longitude"),
        ("lat", "lon"),
    ):
        if latitude_key in alert and longitude_key in alert:
            result = _valid_coordinate_values(
                alert.get(latitude_key),
                alert.get(longitude_key),
            )
            if result:
                return result
    source_data = alert.get("source_data")
    if isinstance(source_data, dict):
        for latitude_key, longitude_key in (
            ("latitude", "longitude"),
            ("lat", "lon"),
        ):
            if latitude_key in source_data and longitude_key in source_data:
                result = _valid_coordinate_values(
                    source_data.get(latitude_key),
                    source_data.get(longitude_key),
                )
                if result:
                    return result
        rss_fields = source_data.get("rss_fields")
        if isinstance(rss_fields, dict):
            for key in ("circle", "point", "coordinates"):
                value = rss_fields.get(key)
                if isinstance(value, list):
                    value = value[0] if value else None
                if isinstance(value, str):
                    match = re.match(
                        r"^\s*(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)",
                        value,
                    )
                    if match:
                        result = _valid_coordinate_values(match.group(1), match.group(2))
                        if result:
                            return result
    return None


def _sachet_alerts_near_route(coordinates):
    try:
        feed = get_sachet_feed()
    except SachetFeedDatabaseUnavailable:
        return {
            "status": "unavailable",
            "alerts": [],
            "alerts_without_coordinates": 0,
            "count": 0,
            "last_successful_check_at": None,
        }

    observations = []
    without_coordinates = 0
    alerts = feed.get("alerts") or []
    for alert in alerts:
        explicit = _explicit_alert_coordinates(alert)
        if explicit is None:
            without_coordinates += 1
            continue
        latitude, longitude = explicit
        distance = min(
            _distance_to_segment_meters(
                {"latitude": latitude, "longitude": longitude},
                start,
                end,
            )
            for start, end in zip(coordinates, coordinates[1:])
        )
        if distance <= ROUTE_CORRIDOR_METERS:
            observations.append({
                "alert_id": str(alert.get("alert_id") or alert.get("_id") or ""),
                "latitude": latitude,
                "longitude": longitude,
                "headline": alert.get("title"),
                "description": alert.get("description"),
                "source_name": alert.get("source_name"),
                "source_url": alert.get("source_url"),
                "source_published_at": (
                    alert["source_published_at"].isoformat()
                    if isinstance(alert.get("source_published_at"), datetime)
                    else None
                ),
                "affected_location": alert.get("affected_location"),
                "distance_from_route_m": round(distance),
                "source_label": "Official SACHET alert",
            })
    return {
        "status": "available" if observations else (
            "insufficient_location_data" if without_coordinates else "none"
        ),
        "alerts": observations,
        "alerts_without_coordinates": without_coordinates,
        "count": len(observations),
        "last_successful_check_at": (
            feed.get("last_successful_check_at").isoformat()
            if isinstance(feed.get("last_successful_check_at"), datetime)
            else None
        ),
    }


def _weather_assessments(points):
    def assess(point):
        try:
            weather = fetch_weather(point["latitude"], point["longitude"])
        except WeatherProviderError:
            return {
                **point,
                "assessment_status": "unavailable",
                "risk_level": None,
                "score": None,
                "factors": [],
            }
        result = assess_weather(weather, location_name="Route location")
        return {
            **point,
            "assessment_status": result["assessment_status"],
            "risk_level": result["risk_level"],
            "score": result["score"],
            "weather_freshness": result["weather_freshness"],
            "data_completeness": result["data_completeness"],
            "factors": result["factors"],
            "provider": result["provider"],
        }

    with ThreadPoolExecutor(max_workers=len(points) or 1) as executor:
        return list(executor.map(assess, points))


def classify_route_risk(weather_assessments, flood_observations, sachet_alerts=None):
    """Classify only supported evidence; incomplete low weather data remains unknown."""
    observations = flood_observations["observations"]
    official_alerts = (sachet_alerts or {}).get("alerts", [])
    if official_alerts:
        count = len(official_alerts)
        return {
            "level": "High",
            "explanation": (
                f"{count} geographically matched official SACHET alert(s) are within "
                f"{ROUTE_CORRIDOR_METERS} m of the route."
            ),
        }
    if observations:
        verified = [
            item for item in observations
            if item.get("verification_status", "verified") == "verified"
        ]
        count = len(observations)
        if verified:
            return {
                "level": "High",
                "explanation": (
                    f"{count} nearby citizen flood report(s), including "
                    f"{len(verified)} verified flood report(s), are within "
                    f"{ROUTE_CORRIDOR_METERS} m of the route."
                ),
            }
        return {
            "level": "Moderate",
            "explanation": (
                f"{count} pending citizen flood report(s) are within "
                f"{ROUTE_CORRIDOR_METERS} m of the route."
            ),
        }

    levels = [
        item["risk_level"]
        for item in weather_assessments
        if item.get("assessment_status") == "available" and item.get("risk_level")
    ]
    if any(level in ("High", "Very High") for level in levels):
        return {
            "level": "High",
            "explanation": "At least one available route weather assessment is High or Very High.",
        }
    if "Moderate" in levels:
        return {
            "level": "Moderate",
            "explanation": "At least one available route weather assessment is Moderate.",
        }

    all_weather_available = bool(weather_assessments) and all(
        item.get("assessment_status") == "available" for item in weather_assessments
    )
    if (
        all_weather_available
        and all(level == "Low" for level in levels)
        and flood_observations["status"] in ("available", "none")
    ):
        return {
            "level": "Low",
            "explanation": (
                "Available weather assessments at sampled route points are Low and the verified "
                "report source was checked. This does not verify road conditions or establish safety."
            ),
        }

    return {
        "level": "Unknown",
        "explanation": (
            "Available data is insufficient to classify the route. Weather may be missing or stale, "
            "or verified flood-report data could not be checked."
        ),
    }


def assess_safe_route(origin, destination):
    route, alternatives = get_driving_routes(origin, destination)
    coordinates = route["geometry"]["coordinates"]
    flood_observations = _reports_near_route(coordinates)
    sachet_alerts = _sachet_alerts_near_route(coordinates)
    samples = _sample_route_points(coordinates)
    weather_assessments = _weather_assessments(samples)
    risk = classify_route_risk(weather_assessments, flood_observations, sachet_alerts)

    risk_factors = []
    for observation in flood_observations["observations"]:
        verification = observation["verification_status"]
        risk_factors.append({
            "type": f"{verification}_flood_report",
            "severity": observation["severity"],
            "detail": (
                f"Citizen-submitted {verification} {observation['severity']} flood report near route "
                f"({observation['distance_from_route_m']} m from the route)."
            ),
        })
    for alert in sachet_alerts["alerts"]:
        risk_factors.append({
            "type": "official_sachet_alert",
            "severity": "high",
            "detail": (
                f"Official SACHET alert near route "
                f"({alert['distance_from_route_m']} m from the route): {alert['headline'] or 'Headline unavailable'}"
            ),
        })
    for index, assessment in enumerate(weather_assessments, start=1):
        if assessment.get("risk_level"):
            risk_factors.append({
                "type": "weather",
                "severity": assessment["risk_level"],
                "detail": f"Sample {index}: {assessment['risk_level']} weather-based indicator.",
            })
    if flood_observations["status"] == "none":
        risk_factors.append({
            "type": "data_limit",
            "severity": "unknown",
            "detail": "No nearby citizen flood reports were found; absence of reports does not establish safety.",
        })
    elif flood_observations["status"] == "unavailable":
        risk_factors.append({
            "type": "data_limit",
            "severity": "unknown",
            "detail": "Citizen flood reports could not be checked because MongoDB is unavailable.",
        })
    elif flood_observations["status"] == "insufficient_location_data":
        risk_factors.append({
            "type": "data_limit",
            "severity": "unknown",
            "detail": (
                f"{flood_observations['reports_without_coordinates']} citizen report(s) "
                "do not contain usable coordinates and were not included in geographic assessment."
            ),
        })

    return {
        "origin": origin,
        "destination": destination,
        "route": route,
        "alternatives": alternatives,
        "routing": {
            "provider": ROUTING_SOURCE,
            "url": "https://project-osrm.org/",
        },
        "distance_km": round(route["distance_m"] / 1000, 2),
        "duration_minutes": round(route["duration_s"] / 60),
        "risk_classification": risk,
        "risk_factors": risk_factors,
        "flood_observations": flood_observations,
        "sachet_alerts": sachet_alerts,
        "hazard_proximity_m": ROUTE_CORRIDOR_METERS,
        "weather_assessments": weather_assessments,
        "weather_provider": {
            "name": "Open-Meteo",
            "attribution_url": "https://open-meteo.com/",
        },
        "limitations": (
            "Weather assessments use model-based precipitation at up to three points on the route. "
            "Citizen reports and geographically matched SACHET records are proximity indicators only. "
            "These sources do not confirm road closures, flood depth, or conditions between sampled points."
        ),
        "assessed_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def store_route_assessment(assessment):
    """Save only route coordinates, summary risk, factors, and provider sources."""
    try:
        collection = check_mongodb_and_prepare_schema()["route_assessments"]
        document = {
            "_id": str(uuid4()),
            "origin": assessment["origin"],
            "destination": assessment["destination"],
            "assessed_at": datetime.fromisoformat(
                assessment["assessed_at"].replace("Z", "+00:00")
            ),
            "distance_m": assessment["route"]["distance_m"],
            "duration_s": assessment["route"]["duration_s"],
            "risk_classification": assessment["risk_classification"],
            "risk_factors": assessment["risk_factors"],
            "routing_source": assessment["routing"]["provider"],
            "weather_source": assessment["weather_provider"]["name"],
            "flood_report_status": assessment["flood_observations"]["status"],
        }
        collection.insert_one(document)
        return {"status": "stored", "stored_at": assessment["assessed_at"]}
    except (MongoDBConfigurationError, PyMongoError, KeyError, TypeError, ValueError) as exc:
        raise RouteStorageError from exc
