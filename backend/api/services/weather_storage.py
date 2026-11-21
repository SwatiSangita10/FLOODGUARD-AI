"""Persist successful Open-Meteo snapshots with per-location deduplication."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pymongo.errors import PyMongoError

from database.mongodb import (
    MongoDBConfigurationError,
    check_mongodb_and_prepare_schema,
)

SNAPSHOT_REFRESH_INTERVAL = timedelta(minutes=10)


class WeatherStorageError(Exception):
    """Raised when a retrieved weather snapshot cannot be persisted."""


def store_weather_snapshot(weather, *, location_name=None):
    location = weather["location"]
    latitude = round(float(location.get("requested_latitude", location["latitude"])), 5)
    longitude = round(float(location.get("requested_longitude", location["longitude"])), 5)
    fetched_at = datetime.fromisoformat(weather["fetched_at"].replace("Z", "+00:00"))
    cutoff = fetched_at - SNAPSHOT_REFRESH_INTERVAL

    try:
        database = check_mongodb_and_prepare_schema()
        collection = database["weather_records"]
        recent = collection.find_one(
            {
                "latitude": latitude,
                "longitude": longitude,
                "fetched_at": {"$gte": cutoff},
            },
            {"fetched_at": 1},
            sort=[("fetched_at", -1)],
        )
        if recent:
            stored_at = recent["fetched_at"]
            if stored_at.tzinfo is None:
                stored_at = stored_at.replace(tzinfo=timezone.utc)
            return {
                "status": "recent_snapshot_exists",
                "stored_at": stored_at.isoformat().replace("+00:00", "Z"),
            }

        document = {
            "_id": str(uuid4()),
            "location_name": location_name,
            "latitude": latitude,
            "longitude": longitude,
            "model_latitude": location["latitude"],
            "model_longitude": location["longitude"],
            "timezone": location["timezone"],
            "current": weather["current"],
            "hourly": weather["hourly"],
            "daily": weather["daily"],
            "source": weather["source"]["name"],
            "fetched_at": fetched_at,
        }
        collection.insert_one(document)
        return {"status": "stored", "stored_at": weather["fetched_at"]}
    except (MongoDBConfigurationError, PyMongoError, KeyError, TypeError, ValueError) as exc:
        raise WeatherStorageError from exc
