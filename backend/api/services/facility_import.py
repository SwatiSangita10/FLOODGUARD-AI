"""Idempotent importer for explicitly curated public facility records."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from pymongo.errors import DuplicateKeyError

from .official_facilities import OFFICIAL_FACILITIES
from .resources import (
    ResourceAlreadyExists,
    _facility_key,
    _find_existing_facility,
    _collection,
)


def _record_for_import(source_record):
    record = deepcopy(source_record)
    record.setdefault("state", None)
    record.setdefault("address", None)
    record.setdefault("district", None)
    record.setdefault("block", None)
    record.setdefault("gram_panchayat", None)
    record.setdefault("village", None)
    record.setdefault("latitude", None)
    record.setdefault("longitude", None)
    record.setdefault("contact_number", None)
    record.setdefault("operating_hours", None)
    record.setdefault("capacity", None)
    record.setdefault("is_active", True)
    record["_id"] = str(uuid5(
        NAMESPACE_URL,
        f"floodguard-facility:{record['source_name']}:{record['source_record_id']}",
    ))
    record["facility_key"] = _facility_key(record)
    return record


def import_official_facilities(*, apply=False, records=OFFICIAL_FACILITIES):
    collection = _collection()
    summary = {
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "preserved_verified": 0,
    }
    now = datetime.now(timezone.utc)

    for source_record in records:
        candidate = _record_for_import(source_record)
        existing = _find_existing_facility(collection, candidate)
        if existing and existing.get("verification_status") == "verified":
            summary["preserved_verified"] += 1
            continue

        if existing:
            updates = {}
            for key, value in candidate.items():
                if key in {"_id", "created_at", "updated_at"}:
                    continue
                if value is None or value == "":
                    continue
                if key == "is_active" and existing.get("is_active") is False:
                    continue
                if existing.get(key) != value:
                    updates[key] = value
            if not updates:
                summary["unchanged"] += 1
                continue
            updates["updated_at"] = now
            if apply:
                try:
                    collection.update_one(
                        {"_id": existing["_id"]},
                        {"$set": updates},
                    )
                except DuplicateKeyError as exc:
                    raise ResourceAlreadyExists from exc
            summary["updated"] += 1
            continue

        candidate["created_at"] = now
        candidate["updated_at"] = now
        if apply:
            try:
                collection.insert_one(candidate)
            except DuplicateKeyError as exc:
                raise ResourceAlreadyExists from exc
        summary["created"] += 1

    return summary
