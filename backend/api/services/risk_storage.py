"""Best-effort persistence for explainable risk assessment snapshots."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pymongo.errors import PyMongoError

from database.mongodb import (
    MongoDBConfigurationError,
    check_mongodb_and_prepare_schema,
)


SNAPSHOT_DEDUPLICATION_INTERVAL = timedelta(minutes=10)


class RiskStorageError(Exception):
    """Raised when an assessment snapshot cannot be persisted."""


def store_risk_assessment(assessment):
    location = assessment["location"]
    latitude = round(float(location["latitude"]), 5)
    longitude = round(float(location["longitude"]), 5)
    assessed_at = datetime.fromisoformat(assessment["assessed_at"].replace("Z", "+00:00"))
    point = {"type": "Point", "coordinates": [longitude, latitude]}
    fingerprint_data = {
        "score": assessment["score"],
        "risk_level": assessment["risk_level"],
        "factors": assessment["factors"],
        "provider_timestamp": assessment["weather_freshness"]["provider_timestamp"],
        "provider": assessment["provider"].get("name"),
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    try:
        collection = check_mongodb_and_prepare_schema()["risk_assessments"]
        cutoff = assessed_at - SNAPSHOT_DEDUPLICATION_INTERVAL
        recent = collection.find_one(
            {
                "location": point,
                "assessment_fingerprint": fingerprint,
                "assessed_at": {"$gte": cutoff},
            },
            {"assessed_at": 1},
            sort=[("assessed_at", -1)],
        )
        if recent:
            stored_at = recent["assessed_at"]
            if stored_at.tzinfo is None:
                stored_at = stored_at.replace(tzinfo=timezone.utc)
            return {
                "status": "recent_snapshot_exists",
                "stored_at": stored_at.isoformat().replace("+00:00", "Z"),
            }

        document = {
            "_id": str(uuid4()),
            "location": point,
            "location_name": location["name"],
            "latitude": latitude,
            "longitude": longitude,
            "risk_score": assessment["score"],
            "risk_level": assessment["risk_level"],
            "assessment_factors": assessment["factors"],
            "explanation": assessment["explanation"],
            "assessed_at": assessed_at,
            "weather_provider": assessment["provider"].get("name"),
            "weather_timestamp": assessment["weather_freshness"]["provider_timestamp"],
            "weather_fetched_at": assessment["weather_freshness"]["fetched_at"],
            "assessment_fingerprint": fingerprint,
        }
        collection.insert_one(document)
        return {"status": "stored", "stored_at": assessment["assessed_at"]}
    except (MongoDBConfigurationError, PyMongoError, KeyError, TypeError, ValueError) as exc:
        raise RiskStorageError from exc
