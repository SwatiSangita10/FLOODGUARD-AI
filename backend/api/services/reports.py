"""MongoDB and local-media operations for citizen flood reports."""
from datetime import datetime, timezone
from uuid import uuid4

from django.core.files.storage import default_storage
from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from api.serializers import PHOTO_FORMATS
from database.mongodb import (
    MongoDBConfigurationError,
    check_mongodb_and_prepare_schema,
)


class ReportDatabaseUnavailable(Exception):
    """Raised when report storage cannot reach MongoDB."""


class ReportPhotoStorageUnavailable(Exception):
    """Raised when local media storage cannot save an uploaded photo."""


def get_reports_collection():
    try:
        database = check_mongodb_and_prepare_schema()
        return database["flood_reports"]
    except (MongoDBConfigurationError, PyMongoError) as exc:
        raise ReportDatabaseUnavailable from exc


def _save_photo(upload):
    extension = PHOTO_FORMATS[upload.validated_image_format]
    safe_name = f"reports/{uuid4().hex}.{extension}"
    try:
        stored_name = default_storage.save(safe_name, upload)
        return stored_name, default_storage.url(stored_name)
    except Exception as exc:
        raise ReportPhotoStorageUnavailable from exc


def _delete_photo(photo_path):
    if not photo_path:
        return
    try:
        default_storage.delete(photo_path)
    except Exception:
        # Preserve the original database error; orphan cleanup can be retried later.
        pass


def _normalize_report(document):
    result = dict(document)
    created_at = result.get("created_at")
    if created_at is not None and created_at.tzinfo is None:
        result["created_at"] = created_at.replace(tzinfo=timezone.utc)
    return result


def create_flood_report(validated_data):
    payload = dict(validated_data)
    photo = payload.pop("photo", None)
    photo_path = None
    photo_url = None

    if photo is not None:
        photo_path, photo_url = _save_photo(photo)

    report_id = str(uuid4())
    document = {
        "_id": report_id,
        "location_name": payload["location_name"],
        "latitude": float(payload["latitude"]),
        "longitude": float(payload["longitude"]),
        "location": {
            "type": "Point",
            "coordinates": [float(payload["longitude"]), float(payload["latitude"])],
        },
        "severity": payload["severity"],
        "description": payload["description"],
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "photo_url": photo_url,
    }
    if payload.get("water_level") is not None:
        document["water_level"] = float(payload["water_level"])

    try:
        get_reports_collection().insert_one(document)
    except ReportDatabaseUnavailable:
        _delete_photo(photo_path)
        raise
    except PyMongoError as exc:
        _delete_photo(photo_path)
        raise ReportDatabaseUnavailable from exc

    return _normalize_report(document)


def list_flood_reports(*, severity=None, status=None, limit=20, offset=0):
    query = {}
    if severity:
        query["severity"] = severity
    if status:
        query["status"] = status

    try:
        collection = get_reports_collection()
        total = collection.count_documents(query)
        cursor = (
            collection.find(query)
            .sort("created_at", DESCENDING)
            .skip(offset)
            .limit(limit)
        )
        reports = [_normalize_report(document) for document in cursor]
    except ReportDatabaseUnavailable:
        raise
    except PyMongoError as exc:
        raise ReportDatabaseUnavailable from exc

    return {"count": total, "limit": limit, "offset": offset, "results": reports}


def list_flood_reports_near_route(coordinates, *, status=None, limit=500):
    """Return reports inside a route bounding box; exact route distance is calculated by the caller."""
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return {"count": 0, "with_coordinates": 0, "without_coordinates": 0, "results": []}

    longitudes = [pair[0] for pair in coordinates if isinstance(pair, list) and len(pair) == 2]
    latitudes = [pair[1] for pair in coordinates if isinstance(pair, list) and len(pair) == 2]
    if not longitudes or not latitudes:
        return {"count": 0, "with_coordinates": 0, "without_coordinates": 0, "results": []}

    buffer_degrees = 0.01
    query = {
        "location": {
            "$geoWithin": {
                "$box": [
                    [min(longitudes) - buffer_degrees, min(latitudes) - buffer_degrees],
                    [max(longitudes) + buffer_degrees, max(latitudes) + buffer_degrees],
                ]
            }
        }
    }
    if status:
        query["status"] = status

    try:
        collection = get_reports_collection()
        cursor = collection.find(query).sort("created_at", DESCENDING).limit(limit)
        results = [_normalize_report(document) for document in cursor]
        missing_query = dict(query)
        missing_query.pop("location", None)
        missing_query["$or"] = [
            {"location": {"$exists": False}},
            {"location": None},
            {"latitude": {"$exists": False}},
            {"longitude": {"$exists": False}},
        ]
        missing_coordinates = collection.count_documents(missing_query)
    except ReportDatabaseUnavailable:
        raise
    except PyMongoError as exc:
        raise ReportDatabaseUnavailable from exc

    with_coordinates = []
    without_coordinates = 0
    for report in results:
        if _valid_report_coordinate(report):
            with_coordinates.append(report)
        else:
            without_coordinates += 1
    return {
        "count": len(results),
        "with_coordinates": len(with_coordinates),
        "without_coordinates": missing_coordinates,
        "results": with_coordinates,
    }


def _valid_report_coordinate(report):
    try:
        latitude = float(report["latitude"])
        longitude = float(report["longitude"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


def get_flood_report(report_id):
    try:
        document = get_reports_collection().find_one({"_id": report_id})
    except ReportDatabaseUnavailable:
        raise
    except PyMongoError as exc:
        raise ReportDatabaseUnavailable from exc

    return _normalize_report(document) if document else None
