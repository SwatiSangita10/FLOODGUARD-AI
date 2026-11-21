"""Stored official alerts and transparent, source-labelled in-app advisories."""
import math
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from api.services.reports import ReportDatabaseUnavailable, list_flood_reports
from api.services.risk_assessment import assess_weather
from api.services.weather import WeatherProviderError, fetch_weather
from database.mongodb import (
    MongoDBConfigurationError,
    check_mongodb_and_prepare_schema,
)


WEATHER_ALERT_LIFETIME = timedelta(hours=1)
COMMUNITY_ALERT_LIFETIME = timedelta(hours=24)
NOTIFICATION_LIFETIME = timedelta(days=90)
COMMUNITY_ALERT_RADIUS_METERS = 500
ALERT_PAGE_SIZE = 20


class AlertDatabaseUnavailable(Exception):
    """Raised when alert or notification data cannot be accessed."""


def _collections():
    try:
        database = check_mongodb_and_prepare_schema()
        return database["flood_alerts"], database["user_notifications"]
    except (MongoDBConfigurationError, PyMongoError) as exc:
        raise AlertDatabaseUnavailable from exc


def _as_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_provider_time(value):
    if not value:
        return None
    try:
        return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (AttributeError, TypeError, ValueError):
        return None


def _distance_meters(first, second):
    latitude1 = math.radians(first["latitude"])
    latitude2 = math.radians(second["latitude"])
    latitude_delta = latitude2 - latitude1
    longitude_delta = math.radians(second["longitude"] - first["longitude"])
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(latitude1) * math.cos(latitude2)
        * math.sin(longitude_delta / 2) ** 2
    )
    return 6_371_000 * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def _weather_alert_document(assessment, latitude, longitude, location_name, now):
    risk_level = assessment["risk_level"]
    factors = assessment["factors"]
    details = "; ".join(factor["explanation"] for factor in factors)
    return {
        "_id": f"weather:{latitude:.4f}:{longitude:.4f}",
        "title": f"Weather-based flood advisory · {location_name or 'selected location'}",
        "description": (
            f"Open-Meteo's preliminary weather indicator is {risk_level} "
            f"({assessment['score']}/100). {details} This is not an official warning "
            "and does not confirm flooding."
        ),
        "severity": "Advisory",
        "affected_location": location_name or "Selected location",
        "district": None,
        "source_type": "weather",
        "source_name": "Open-Meteo",
        "source_url": "https://open-meteo.com/",
        "source_verification_status": "not_applicable",
        "source_published_at": _parse_provider_time(
            assessment["weather_freshness"].get("provider_timestamp")
        ),
        "last_verified_at": None,
        "created_at": now,
        "expires_at": now + WEATHER_ALERT_LIFETIME,
        "status": "active",
        "source_record_id": None,
        "source_data": {
            "risk_level": risk_level,
            "score": assessment["score"],
            "factors": factors,
            "weather_freshness": assessment["weather_freshness"],
            "data_completeness": assessment["data_completeness"],
        },
        "generated_by": "weather_assessment",
        "updated_at": now,
    }


def _sync_weather_alert(collection, latitude, longitude, location_name, now):
    try:
        weather = fetch_weather(latitude, longitude)
    except WeatherProviderError:
        return "unavailable"
    assessment = assess_weather(weather, location_name=location_name)
    alert_id = f"weather:{latitude:.4f}:{longitude:.4f}"
    if (
        assessment["assessment_status"] == "available"
        and assessment["risk_level"] in ("Moderate", "High", "Very High")
    ):
        collection.replace_one(
            {"_id": alert_id},
            _weather_alert_document(assessment, latitude, longitude, location_name, now),
            upsert=True,
        )
    else:
        collection.update_one(
            {"_id": alert_id, "status": "active"},
            {"$set": {"status": "resolved", "updated_at": now}},
        )
    return assessment["assessment_status"]


def _community_alert_document(report, now):
    created_at = _as_utc(report["created_at"])
    location_name = report["location_name"]
    return {
        "_id": f"community:{report['report_id']}",
        "title": f"Verified community flood report · {location_name}",
        "description": (
            f"A community-submitted {report['severity']} flood report at {location_name} "
            "is marked verified in FLOODGUARD. Community information may not reflect "
            "current conditions and is not an official government alert."
        ),
        "severity": "Warning",
        "affected_location": location_name,
        "district": None,
        "source_type": "community",
        "source_name": "FLOODGUARD verified citizen report",
        "source_url": None,
        "source_verification_status": "verified",
        "source_published_at": created_at,
        "last_verified_at": None,
        "created_at": now,
        "expires_at": created_at + COMMUNITY_ALERT_LIFETIME,
        "status": "active",
        "source_record_id": report["report_id"],
        "source_data": {
            "report_id": report["report_id"],
            "severity": report["severity"],
            "location_name": location_name,
            "latitude": report["latitude"],
            "longitude": report["longitude"],
            "report_created_at": created_at.isoformat(),
        },
        "generated_by": "verified_reports",
        "updated_at": now,
    }


def _sync_community_alerts(collection, now):
    try:
        page = list_flood_reports(status="verified", limit=100, offset=0)
    except ReportDatabaseUnavailable:
        return {"status": "unavailable", "verified_reports_checked": 0}

    reports = []
    for report in page["results"]:
        created_at = _as_utc(report["created_at"])
        if created_at <= now and now - created_at <= COMMUNITY_ALERT_LIFETIME:
            reports.append(report)
    report_ids = set()
    for report in reports:
        nearby_count = sum(
            _distance_meters(report, other) <= COMMUNITY_ALERT_RADIUS_METERS
            for other in reports
            if other["report_id"] != report["report_id"]
        )
        if report["severity"] in ("high", "critical") or nearby_count:
            alert = _community_alert_document(report, now)
            collection.replace_one({"_id": alert["_id"]}, alert, upsert=True)
            report_ids.add(report["report_id"])

    if page["count"] <= 100:
        collection.update_many(
            {
                "source_type": "community",
                "generated_by": "verified_reports",
                "status": "active",
                "source_record_id": {"$nin": list(report_ids)},
            },
            {"$set": {"status": "resolved", "updated_at": now}},
        )
    return {
        "status": "partial" if page["count"] > 100 else "available",
        "verified_reports_checked": len(page["results"]),
    }


def _active_query(params, now):
    clauses = [
        {"status": "active"},
        {"$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}]},
    ]
    for field in ("severity", "source_type", "source_verification_status"):
        if params.get(field):
            clauses.append({field: params[field]})
    if params.get("district"):
        clauses.append({
            "district": {
                "$regex": f"^{re.escape(params['district'])}$",
                "$options": "i",
            },
        })
    if params.get("search"):
        pattern = {"$regex": re.escape(params["search"]), "$options": "i"}
        clauses.append({
            "$or": [
                {"title": pattern},
                {"description": pattern},
                {"affected_location": pattern},
                {"district": pattern},
            ],
        })
    return {"$and": clauses}


def list_active_alerts(params):
    alert_collection, notification_collection = _collections()
    now = datetime.now(timezone.utc)
    sources = {
        "weather": "not_requested",
        "verified_reports": "unavailable",
    }
    if "latitude" in params:
        try:
            sources["weather"] = _sync_weather_alert(
                alert_collection,
                params["latitude"],
                params["longitude"],
                params.get("location_name"),
                now,
            )
        except PyMongoError as exc:
            raise AlertDatabaseUnavailable from exc
    try:
        sources["verified_reports"] = _sync_community_alerts(alert_collection, now)["status"]
        query = _active_query(params, now)
        count = alert_collection.count_documents(query)
        documents = list(
            alert_collection.find(query)
            .sort("created_at", DESCENDING)
            .skip(params["offset"])
            .limit(params["limit"])
        )
        active_ids = [
            item["_id"]
            for item in alert_collection.find(query, {"_id": 1})
        ]
        client_id = str(params["client_id"]) if params.get("client_id") else None
        read_ids = set()
        if client_id and active_ids:
            read_ids = {
                item["alert_id"]
                for item in notification_collection.find(
                    {"client_id": client_id, "alert_id": {"$in": active_ids}},
                    {"alert_id": 1},
                )
            }
    except (AlertDatabaseUnavailable, ReportDatabaseUnavailable):
        raise
    except PyMongoError as exc:
        raise AlertDatabaseUnavailable from exc

    for document in documents:
        document["is_read"] = document["_id"] in read_ids
    read_count = len(read_ids)
    return {
        "count": count,
        "unread_count": max(0, count - read_count),
        "limit": params["limit"],
        "offset": params["offset"],
        "next_offset": (
            params["offset"] + len(documents)
            if params["offset"] + len(documents) < count
            else None
        ),
        "results": documents,
        "sources": sources,
    }


def get_alert(alert_id, client_id=None):
    collection, notification_collection = _collections()
    try:
        document = collection.find_one({"_id": alert_id})
        if document is not None and client_id:
            notification = notification_collection.find_one({
                "client_id": str(client_id),
                "alert_id": alert_id,
            })
            document["is_read"] = notification is not None
    except PyMongoError as exc:
        raise AlertDatabaseUnavailable from exc
    if document is None:
        return None
    document.setdefault("is_read", False)
    expires_at = document.get("expires_at")
    if (
        document.get("status") == "active"
        and expires_at is not None
        and _as_utc(expires_at) <= datetime.now(timezone.utc)
    ):
        document["status"] = "expired"
    return document


def create_managed_alert(validated_data):
    now = datetime.now(timezone.utc)
    document = {
        "_id": str(uuid4()),
        **validated_data,
        "district": validated_data.get("district") or None,
        "created_at": now,
        "status": "active",
        "source_record_id": None,
        "source_data": {},
        "generated_by": "staff_managed",
        "updated_at": now,
    }
    try:
        collection, _ = _collections()
        collection.insert_one(document)
    except (AlertDatabaseUnavailable, PyMongoError) as exc:
        raise AlertDatabaseUnavailable from exc
    return document


def mark_alert_read(alert_id, client_id):
    alert_collection, notification_collection = _collections()
    now = datetime.now(timezone.utc)
    try:
        alert = alert_collection.find_one({"_id": alert_id, "status": "active"})
        if alert is None:
            return None
        expires_at = alert.get("expires_at")
        if expires_at is not None and _as_utc(expires_at) <= now:
            return None
        key = {"client_id": str(client_id), "alert_id": alert_id}
        notification_collection.update_one(
            key,
            {
                "$setOnInsert": {
                    **key,
                    "read_at": now,
                    "expires_at": now + NOTIFICATION_LIFETIME,
                },
            },
            upsert=True,
        )
        return notification_collection.find_one(key)
    except PyMongoError as exc:
        raise AlertDatabaseUnavailable from exc
