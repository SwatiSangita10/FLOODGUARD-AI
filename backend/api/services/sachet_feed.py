"""Backend-only reader for the official NDMA SACHET Odisha RSS feed."""
import re
import socket
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from pymongo.errors import PyMongoError

from database.mongodb import (
    MongoDBConfigurationError,
    check_mongodb_and_prepare_schema,
)


SACHET_PORTAL_URL = "https://sachet.ndma.gov.in/CapFeed"
SACHET_FEED_URL = (
    "https://sachet.ndma.gov.in/cap_public_website/rss/rss_odisha.xml"
)
SACHET_STATE_ID = "odisha"
REQUEST_TIMEOUT_SECONDS = 8
MAX_FEED_BYTES = 2 * 1024 * 1024
MAX_FEED_ITEMS = 1000
MAX_CACHED_ALERTS = 100
MIN_REFRESH_INTERVAL = timedelta(seconds=30)
OFFICIAL_LINK_HOSTS = ("sachet.ndma.gov.in", "ndma.gov.in")


class SachetFeedDatabaseUnavailable(Exception):
    """Raised when the MongoDB alert snapshot cannot be read or written."""


class SachetFeedError(Exception):
    """A provider or feed-format failure, safe to retain as a status code."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class _PlainTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _local_name(tag):
    return tag.rsplit("}", 1)[-1].casefold()


def _element_text(element):
    return "".join(element.itertext()).strip()


def _find_text(element, names):
    names = {name.casefold() for name in names}
    for child in list(element):
        if _local_name(child.tag) in names:
            value = _element_text(child)
            if value:
                return value
    for child in element.iter():
        if child is element:
            continue
        if _local_name(child.tag) in names:
            value = _element_text(child)
            if value:
                return value
    return None


def _parse_datetime(value):
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _plain_description(value):
    if not value:
        return None
    parser = _PlainTextExtractor()
    parser.feed(value)
    text = " ".join(" ".join(parser.parts).split())
    return text or None


def _explicit_sachet_coordinates(raw_fields):
    """Extract coordinates only when the source XML explicitly provides them."""
    if not isinstance(raw_fields, dict):
        return None
    for key in ("circle", "point", "coordinates", "latitude", "longitude"):
        value = raw_fields.get(key)
        if isinstance(value, list):
            value = value[0] if value else None
        if not isinstance(value, str):
            continue
        match = re.match(
            r"^\s*(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)",
            value.strip(),
        )
        if not match:
            continue
        latitude = float(match.group(1))
        longitude = float(match.group(2))
        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
            return latitude, longitude

    latitude_value = raw_fields.get("latitude")
    longitude_value = raw_fields.get("longitude")
    if isinstance(latitude_value, list):
        latitude_value = latitude_value[0] if latitude_value else None
    if isinstance(longitude_value, list):
        longitude_value = longitude_value[0] if longitude_value else None
    try:
        latitude = float(latitude_value)
        longitude = float(longitude_value)
    except (TypeError, ValueError):
        return None
    if -90 <= latitude <= 90 and -180 <= longitude <= 180:
        return latitude, longitude
    return None


def _official_link(value):
    if not value:
        return None
    resolved = urljoin(SACHET_FEED_URL, value)
    parts = urlsplit(resolved)
    hostname = (parts.hostname or "").lower()
    if (
        parts.scheme != "https"
        or not any(
            hostname == host or hostname.endswith(f".{host}")
            for host in OFFICIAL_LINK_HOSTS
        )
    ):
        return None
    return resolved


def parse_sachet_rss(content, *, now=None):
    """Parse RSS 2.0 entries without resolving DTDs or external entities."""
    now = now or datetime.now(timezone.utc)
    if len(content) > MAX_FEED_BYTES:
        raise SachetFeedError("feed_too_large")
    if b"\x00" in content:
        raise SachetFeedError("unsupported_xml_encoding")
    try:
        xml_text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SachetFeedError("unsupported_xml_encoding") from exc
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", xml_text, re.IGNORECASE):
        raise SachetFeedError("unsafe_xml")

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise SachetFeedError("invalid_xml") from exc

    if _local_name(root.tag) != "rss" or root.attrib.get("version") != "2.0":
        raise SachetFeedError("unsupported_feed_format")
    channel = next(
        (child for child in list(root) if _local_name(child.tag) == "channel"),
        None,
    )
    if channel is None:
        raise SachetFeedError("missing_channel")

    items = [child for child in list(channel) if _local_name(child.tag) == "item"]
    if len(items) > MAX_FEED_ITEMS:
        raise SachetFeedError("too_many_items")

    documents = []
    seen_identifiers = set()
    duplicate_count = 0
    skipped_count = 0
    for item in items:
        identifier = _find_text(item, {"guid", "identifier"})
        if not identifier:
            skipped_count += 1
            continue
        if identifier in seen_identifiers:
            duplicate_count += 1
            continue
        seen_identifiers.add(identifier)

        title = _find_text(item, {"headline", "title"})
        raw_description = _find_text(item, {"description"})
        category = _find_text(item, {"category"})
        author = _find_text(item, {"author", "sender"})
        raw_link = _find_text(item, {"link"})
        published_text = _find_text(item, {"pubdate", "published", "sent"})
        effective_text = _find_text(item, {"effective"})
        expires_text = _find_text(item, {"expires"})
        expires_at = _parse_datetime(expires_text)

        raw_fields = {}
        for child in item.iter():
            if child is item:
                continue
            field_name = _local_name(child.tag)
            field_value = _element_text(child)
            if not field_value:
                continue
            if field_name in raw_fields:
                previous = raw_fields[field_name]
                if not isinstance(previous, list):
                    raw_fields[field_name] = [previous]
                raw_fields[field_name].append(field_value)
            else:
                raw_fields[field_name] = field_value

        explicit_coordinates = _explicit_sachet_coordinates(raw_fields)
        document = {
            "_id": f"sachet:{identifier}",
            "title": title,
            "description": _plain_description(raw_description),
            "severity": _find_text(item, {"severity"}),
            "urgency": _find_text(item, {"urgency"}),
            "event_type": _find_text(item, {"event"}),
            "affected_location": _find_text(item, {"areadesc", "area"}),
            "district": None,
            "source_type": "sachet",
            "source_name": "NDMA SACHET",
            "source_url": _official_link(raw_link),
            "source_verification_status": "verified",
            "source_published_at": _parse_datetime(published_text),
            "effective_at": _parse_datetime(effective_text),
            "last_verified_at": now,
            "created_at": now,
            "expires_at": expires_at,
            "status": (
                "expired" if expires_at is not None and expires_at <= now
                else "feed_entry"
            ),
            "source_record_id": identifier,
            "source_data": {
                "official_identifier": identifier,
                "rss_category": category,
                "author": author,
                "raw_description": raw_description,
                "raw_link": raw_link,
                "published_text": published_text,
                "effective_text": effective_text,
                "expires_text": expires_text,
                "rss_fields": raw_fields,
            },
            "feed_snapshot_at": now,
            "updated_at": now,
        }
        if explicit_coordinates:
            document["latitude"], document["longitude"] = explicit_coordinates
            document["location"] = {
                "type": "Point",
                "coordinates": [explicit_coordinates[1], explicit_coordinates[0]],
            }
        documents.append(document)

    if items and not documents:
        raise SachetFeedError("missing_stable_identifiers")
    return {
        "alerts": documents,
        "item_count": len(items),
        "duplicate_count": duplicate_count,
        "skipped_count": skipped_count,
    }


def _fetch_sachet_feed(etag=None, last_modified=None):
    headers = {
        "Accept": "application/rss+xml, application/xml, text/xml;q=0.9",
        "User-Agent": "FloodGuardAI/1.0",
    }
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    request = Request(SACHET_FEED_URL, headers=headers)

    try:
        response = urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS)
    except HTTPError as exc:
        if exc.code == 304:
            return {
                "status": 304,
                "body": None,
                "etag": exc.headers.get("ETag") if exc.headers else None,
                "last_modified": (
                    exc.headers.get("Last-Modified") if exc.headers else None
                ),
            }
        raise SachetFeedError("http_error") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise SachetFeedError("timeout") from exc
    except (URLError, OSError) as exc:
        raise SachetFeedError("network_error") from exc

    try:
        with response:
            final_url = urlsplit(response.geturl())
            if (
                final_url.scheme != "https"
                or (final_url.hostname or "").lower() != "sachet.ndma.gov.in"
            ):
                raise SachetFeedError("unexpected_redirect")
            status = response.getcode()
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
            if status == 304:
                return {
                    "status": 304,
                    "body": None,
                    "etag": etag,
                    "last_modified": last_modified,
                }
            if status != 200:
                raise SachetFeedError("http_error")
            content_type = response.headers.get_content_type().casefold()
            if content_type not in {
                "application/rss+xml",
                "application/xml",
                "text/xml",
            }:
                raise SachetFeedError("unexpected_content_type")
            content = response.read(MAX_FEED_BYTES + 1)
            if len(content) > MAX_FEED_BYTES:
                raise SachetFeedError("feed_too_large")
    except SachetFeedError:
        raise
    except (TimeoutError, socket.timeout) as exc:
        raise SachetFeedError("timeout") from exc
    except OSError as exc:
        raise SachetFeedError("network_error") from exc

    return {
        "status": 200,
        "body": content,
        "etag": etag,
        "last_modified": last_modified,
    }


def _as_utc(value):
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _state_status(state, alerts):
    if state.get("last_error_code"):
        return "stale" if state.get("last_successful_check_at") else "unavailable"
    if not state.get("last_successful_check_at"):
        return "unavailable"
    return "available" if alerts else "empty"


def _read_snapshot(alert_collection, state, now):
    snapshot_at = state.get("content_snapshot_at")
    if snapshot_at is None:
        return []
    query = {
        "source_type": "sachet",
        "feed_snapshot_at": snapshot_at,
        "status": "feed_entry",
        "$or": [
            {"expires_at": None},
            {"expires_at": {"$gt": now}},
        ],
    }
    return list(
        alert_collection.find(query)
        .sort("source_published_at", -1)
        .limit(MAX_CACHED_ALERTS)
    )


def _response(alert_collection, state, now, refresh_status):
    alerts = _read_snapshot(alert_collection, state, now)
    return {
        "status": _state_status(state, alerts),
        "refresh_status": refresh_status,
        "source_name": "NDMA SACHET",
        "source_url": SACHET_PORTAL_URL,
        "feed_url": SACHET_FEED_URL,
        "last_successful_update_at": _as_utc(
            state.get("last_successful_update_at")
        ),
        "last_successful_check_at": _as_utc(
            state.get("last_successful_check_at")
        ),
        "count": len(alerts),
        "duplicate_count": state.get("duplicate_count", 0),
        "skipped_count": state.get("skipped_count", 0),
        "alerts": alerts,
    }


def _record_failure(state_collection, alert_collection, state, now, error_code):
    failure_state = {
        "source_url": SACHET_FEED_URL,
        "last_attempt_at": now,
        "last_error_code": error_code,
    }
    state_collection.update_one(
        {"_id": SACHET_STATE_ID},
        {"$set": failure_state},
        upsert=True,
    )
    state.update(failure_state)
    return _response(alert_collection, state, now, "stale")


def get_sachet_feed(now=None):
    """Refresh the official snapshot, retaining cached records on feed failures."""
    now = now or datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc).replace(
        microsecond=(now.microsecond // 1000) * 1000
    )
    try:
        database = check_mongodb_and_prepare_schema()
        alert_collection = database["flood_alerts"]
        state_collection = database["sachet_feed_state"]
        state = state_collection.find_one({"_id": SACHET_STATE_ID}) or {
            "_id": SACHET_STATE_ID,
        }

        last_attempt = _as_utc(state.get("last_attempt_at"))
        if last_attempt and now - last_attempt < MIN_REFRESH_INTERVAL:
            return _response(alert_collection, state, now, "cached")

        etag = state.get("etag") if state.get("content_snapshot_at") else None
        last_modified = (
            state.get("last_modified")
            if state.get("content_snapshot_at")
            else None
        )
        try:
            fetched = _fetch_sachet_feed(etag, last_modified)
        except SachetFeedError as exc:
            return _record_failure(
                state_collection,
                alert_collection,
                state,
                now,
                exc.code,
            )

        if fetched["status"] == 304:
            success_state = {
                "source_url": SACHET_FEED_URL,
                "last_attempt_at": now,
                "last_successful_check_at": now,
                "last_error_code": None,
            }
            if fetched.get("etag"):
                success_state["etag"] = fetched["etag"]
            if fetched.get("last_modified"):
                success_state["last_modified"] = fetched["last_modified"]
            state_collection.update_one(
                {"_id": SACHET_STATE_ID},
                {"$set": success_state},
                upsert=True,
            )
            state.update(success_state)
            return _response(alert_collection, state, now, "not_modified")

        try:
            parsed = parse_sachet_rss(fetched["body"], now=now)
        except SachetFeedError as exc:
            return _record_failure(
                state_collection,
                alert_collection,
                state,
                now,
                exc.code,
            )
        for document in parsed["alerts"]:
            to_set = {
                key: value
                for key, value in document.items()
                if key != "created_at"
            }
            alert_collection.update_one(
                {"_id": document["_id"]},
                {
                    "$set": to_set,
                    "$setOnInsert": {"created_at": document["created_at"]},
                },
                upsert=True,
            )

        success_state = {
            "source_url": SACHET_FEED_URL,
            "etag": fetched.get("etag"),
            "last_modified": fetched.get("last_modified"),
            "last_attempt_at": now,
            "last_successful_check_at": now,
            "last_successful_update_at": now,
            "content_snapshot_at": now,
            "item_count": parsed["item_count"],
            "duplicate_count": parsed["duplicate_count"],
            "skipped_count": parsed["skipped_count"],
            "last_error_code": None,
        }
        state_collection.update_one(
            {"_id": SACHET_STATE_ID},
            {"$set": success_state},
            upsert=True,
        )
        state.update(success_state)
        return _response(alert_collection, state, now, "updated")
    except (MongoDBConfigurationError, PyMongoError) as exc:
        raise SachetFeedDatabaseUnavailable from exc
