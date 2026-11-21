"""MongoDB-backed, manually managed emergency resource directory."""
import logging
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from bson import ObjectId
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError

from api.serializers import FACILITY_RESOURCE_CATEGORIES
from database.mongodb import (
    MongoDBConfigurationError,
    check_mongodb_and_prepare_schema,
)


class ResourceDatabaseUnavailable(Exception):
    """Raised when the emergency resource collection cannot be accessed."""


class ResourceAlreadyExists(Exception):
    """Raised when a matching facility is already in the directory."""


logger = logging.getLogger(__name__)


def _raise_database_unavailable(cause):
    logger.error(
        "MongoDB emergency resource access failed (%s).",
        type(cause).__name__,
    )
    raise ResourceDatabaseUnavailable from cause


def is_valid_resource_id(resource_id):
    try:
        UUID(str(resource_id))
        return True
    except (ValueError, TypeError, AttributeError):
        return ObjectId.is_valid(str(resource_id))


def _stored_resource_id(resource_id):
    try:
        return str(UUID(str(resource_id)))
    except (ValueError, TypeError, AttributeError):
        if ObjectId.is_valid(str(resource_id)):
            return ObjectId(str(resource_id))
        return None


def _collection():
    try:
        return check_mongodb_and_prepare_schema()["emergency_resources"]
    except (MongoDBConfigurationError, PyMongoError) as exc:
        _raise_database_unavailable(exc)


def _normalize_resource(document):
    result = dict(document)
    result.setdefault("state", None)
    result.setdefault("address", None)
    result.setdefault("district", None)
    result.setdefault("block", None)
    result.setdefault("gram_panchayat", None)
    result.setdefault("village", None)
    result.setdefault("latitude", None)
    result.setdefault("longitude", None)
    result.setdefault("contact_number", None)
    result.setdefault("operating_hours", None)
    result.setdefault("capacity", None)
    result.setdefault("source_record_id", None)
    result.setdefault("verification_status", "unverified")
    result.setdefault("last_verified_at", None)
    result.setdefault("is_active", True)
    result.setdefault("created_at", None)
    result.setdefault("updated_at", None)
    if result.get("verification_status") != "verified" or not result["last_verified_at"]:
        result["verification_status"] = "unverified"
        result["latitude"] = None
        result["longitude"] = None
    for field in ("last_verified_at", "created_at", "updated_at"):
        value = result.get(field)
        if isinstance(value, datetime) and value.tzinfo is None:
            result[field] = value.replace(tzinfo=timezone.utc)
    return result


def _facility_key(document):
    fields = (
        "name",
        "category",
        "state",
        "district",
        "block",
        "gram_panchayat",
        "village",
        "address",
    )
    return "|".join(
        " ".join(str(document.get(field) or "").casefold().split())
        for field in fields
    )


def _find_existing_facility(collection, document):
    source_record_id = document.get("source_record_id")
    if source_record_id:
        existing = collection.find_one({"source_record_id": source_record_id})
        if existing:
            return existing

    facility_key = document.get("facility_key") or _facility_key(document)
    existing = collection.find_one({"facility_key": facility_key})
    if existing:
        return existing

    identity = {
        field: document.get(field)
        for field in (
            "name",
            "category",
            "state",
            "district",
            "block",
            "gram_panchayat",
            "village",
            "address",
        )
    }
    return collection.find_one(identity)


def list_resources(
    *,
    category=None,
    district=None,
    search=None,
    verification_status=None,
    is_active=None,
    limit=20,
    offset=0,
):
    query = {"category": {"$ne": "emergency_helpline"}}
    if is_active is False:
        query["is_active"] = False
    else:
        query["is_active"] = {"$ne": False}
    if category:
        query["category"] = category
    if district:
        query["district"] = {"$regex": f"^{re.escape(district)}$", "$options": "i"}
    if verification_status:
        query["verification_status"] = verification_status
        if verification_status == "verified":
            query["last_verified_at"] = {"$type": "date"}
    if search:
        pattern = {"$regex": re.escape(search), "$options": "i"}
        query["$or"] = [
            {"name": pattern},
            {"address": pattern},
            {"district": pattern},
            {"state": pattern},
            {"block": pattern},
            {"gram_panchayat": pattern},
            {"village": pattern},
        ]

    try:
        collection = _collection()
        count = collection.count_documents(query)
        results = [
            _normalize_resource(document)
            for document in collection.find(query)
            .sort("name", ASCENDING)
            .skip(offset)
            .limit(limit)
        ]
    except ResourceDatabaseUnavailable:
        raise
    except PyMongoError as exc:
        _raise_database_unavailable(exc)

    return {
        "count": count,
        "limit": limit,
        "offset": offset,
        "next_offset": offset + len(results) if offset + len(results) < count else None,
        "results": results,
    }


def list_resource_categories():
    try:
        collection = _collection()
        active_query = {
            "is_active": {"$ne": False},
            "category": {"$ne": "emergency_helpline"},
        }
        districts = collection.distinct(
            "district",
            {
                **active_query,
                "district": {"$type": "string", "$ne": ""},
            },
        )
        total_count = collection.count_documents(active_query)
        verified_count = collection.count_documents({
            **active_query,
            "verification_status": "verified",
            "last_verified_at": {"$type": "date"},
        })
    except ResourceDatabaseUnavailable:
        raise
    except PyMongoError as exc:
        _raise_database_unavailable(exc)
    return {
        "categories": [
            {"value": value, "label": label}
            for value, label in FACILITY_RESOURCE_CATEGORIES
        ],
        "districts": sorted({district for district in districts if district}),
        "total_count": total_count,
        "verified_count": verified_count,
    }


def get_resource(resource_id, *, include_inactive=False):
    stored_id = _stored_resource_id(resource_id)
    if stored_id is None:
        return None
    try:
        document = _collection().find_one({"_id": stored_id})
    except ResourceDatabaseUnavailable:
        raise
    except PyMongoError as exc:
        _raise_database_unavailable(exc)
    if not document or document.get("category") == "emergency_helpline":
        return None
    if not include_inactive and document.get("is_active", True) is False:
        return None
    return _normalize_resource(document)


def create_resource(validated_data):
    now = datetime.now(timezone.utc)
    document = {
        "_id": str(uuid4()),
        "name": validated_data["name"],
        "category": validated_data["category"],
        "state": validated_data.get("state") or None,
        "address": validated_data.get("address") or None,
        "district": validated_data.get("district") or None,
        "block": validated_data.get("block") or None,
        "gram_panchayat": validated_data.get("gram_panchayat") or None,
        "village": validated_data.get("village") or None,
        "latitude": validated_data.get("latitude"),
        "longitude": validated_data.get("longitude"),
        "contact_number": validated_data.get("contact_number") or None,
        "operating_hours": validated_data.get("operating_hours") or None,
        "capacity": validated_data.get("capacity"),
        "source_name": validated_data["source_name"],
        "source_url": validated_data["source_url"],
        "source_record_id": validated_data.get("source_record_id") or None,
        "verification_status": validated_data["verification_status"],
        "last_verified_at": validated_data.get("last_verified_at"),
        "is_active": validated_data.get("is_active", True),
        "created_at": now,
        "updated_at": now,
    }
    document["facility_key"] = _facility_key(document)
    try:
        collection = _collection()
        if _find_existing_facility(collection, document):
            raise ResourceAlreadyExists
        collection.insert_one(document)
    except ResourceAlreadyExists:
        raise
    except DuplicateKeyError as exc:
        raise ResourceAlreadyExists from exc
    except ResourceDatabaseUnavailable:
        raise
    except PyMongoError as exc:
        _raise_database_unavailable(exc)
    return _normalize_resource(document)


def update_resource(resource_id, validated_data):
    stored_id = _stored_resource_id(resource_id)
    if stored_id is None:
        return None
    try:
        collection = _collection()
        existing = collection.find_one({"_id": stored_id})
    except ResourceDatabaseUnavailable:
        raise
    except PyMongoError as exc:
        _raise_database_unavailable(exc)
    if existing is None or existing.get("category") == "emergency_helpline":
        return None

    document = {
        key: value
        for key, value in existing.items()
        if key not in ("_id", "created_at", "updated_at", "facility_key")
    }
    document.update(validated_data)
    document["state"] = document.get("state") or None
    document["address"] = document.get("address") or None
    document["district"] = document.get("district") or None
    document["block"] = document.get("block") or None
    document["gram_panchayat"] = document.get("gram_panchayat") or None
    document["village"] = document.get("village") or None
    document["contact_number"] = document.get("contact_number") or None
    document["operating_hours"] = document.get("operating_hours") or None
    if document.get("verification_status") != "verified":
        document["latitude"] = None
        document["longitude"] = None
    document["facility_key"] = _facility_key(document)
    document["updated_at"] = datetime.now(timezone.utc)

    try:
        duplicate = collection.find_one({
            "facility_key": document["facility_key"],
            "_id": {"$ne": stored_id},
        })
        if duplicate:
            raise ResourceAlreadyExists
        result = collection.update_one({"_id": stored_id}, {"$set": document})
        if not result.matched_count:
            return None
        return get_resource(resource_id, include_inactive=True)
    except ResourceAlreadyExists:
        raise
    except DuplicateKeyError as exc:
        raise ResourceAlreadyExists from exc
    except ResourceDatabaseUnavailable:
        raise
    except PyMongoError as exc:
        _raise_database_unavailable(exc)
