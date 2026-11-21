from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.message import Message
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError
from xml.sax.saxutils import escape

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from api.services import sachet_feed
from api.services.sachet_feed import (
    SACHET_FEED_URL,
    SachetFeedDatabaseUnavailable,
    SachetFeedError,
    get_sachet_feed,
    parse_sachet_rss,
)
from database.mongodb import MongoDBConfigurationError


NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def rss_item(identifier="alert-1", title="Official feed headline", extra=""):
    return (
        "<item>"
        f"<guid>{escape(identifier)}</guid>"
        f"<title>{escape(title)}</title>"
        "<description><![CDATA[<p>Official instructions.</p>]]></description>"
        "<category>Met</category>"
        "<link>https://sachet.ndma.gov.in/alert/alert-1</link>"
        "<author>NDMA</author>"
        "<pubDate>Wed, 21 Oct 2015 07:28:00 GMT</pubDate>"
        f"{extra}"
        "</item>"
    )


def rss_document(*items):
    return (
        '<rss version="2.0"><channel><title>SACHET</title>'
        f'{"".join(items)}'
        "</channel></rss>"
    ).encode()


CAP_FIELDS = (
    '<cap:info xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">'
    "<cap:event>Flood</cap:event>"
    "<cap:urgency>Immediate</cap:urgency>"
    "<cap:severity>Severe</cap:severity>"
    "<cap:effective>2026-11-21T11:00:00Z</cap:effective>"
    "<cap:expires>2099-01-01T00:00:00Z</cap:expires>"
    "<cap:area><cap:areaDesc>Test District</cap:areaDesc></cap:area>"
    "</cap:info>"
)


class MemoryCursor:
    def __init__(self, documents):
        self.documents = list(documents)

    def sort(self, field, direction):
        self.documents.sort(
            key=lambda item: (item.get(field) is not None, item.get(field)),
            reverse=direction < 0,
        )
        return self

    def limit(self, count):
        self.documents = self.documents[:count]
        return self

    def __iter__(self):
        return iter(self.documents)


class MemoryCollection:
    def __init__(self, documents=()):
        self.documents = {item["_id"]: deepcopy(item) for item in documents}
        self.update_calls = []

    def find_one(self, query):
        return deepcopy(self.documents.get(query["_id"]))

    def update_one(self, query, update, upsert=False):
        self.update_calls.append((deepcopy(query), deepcopy(update), upsert))
        existing = self.documents.get(query["_id"])
        if existing is None and not upsert:
            return
        document = deepcopy(existing or {"_id": query["_id"]})
        if existing is None:
            document.update(deepcopy(update.get("$setOnInsert", {})))
        document.update(deepcopy(update.get("$set", {})))
        self.documents[query["_id"]] = document

    def find(self, query):
        now = query["$or"][1]["expires_at"]["$gt"]
        results = []
        for document in self.documents.values():
            if any(document.get(key) != value for key, value in query.items() if key != "$or"):
                continue
            expires_at = document.get("expires_at")
            if expires_at is not None and expires_at <= now:
                continue
            results.append(deepcopy(document))
        return MemoryCursor(results)


class MemoryDatabase:
    def __init__(self, **collections):
        self.collections = collections

    def __getitem__(self, name):
        return self.collections[name]


class FakeResponse:
    def __init__(self, body, *, status=200, etag=None, content_type="application/xml"):
        self.body = body
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if etag:
            self.headers["ETag"] = etag
        self.headers["Last-Modified"] = "Sat, 21 Nov 2026 12:00:00 GMT"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def geturl(self):
        return SACHET_FEED_URL

    def getcode(self):
        return self.status

    def read(self, size):
        return self.body[:size]


def cached_state(snapshot_at):
    return {
        "_id": "odisha",
        "source_url": SACHET_FEED_URL,
        "etag": '"old-etag"',
        "last_modified": "Fri, 20 Nov 2026 12:00:00 GMT",
        "last_attempt_at": NOW - timedelta(minutes=2),
        "last_successful_check_at": snapshot_at,
        "last_successful_update_at": snapshot_at,
        "content_snapshot_at": snapshot_at,
        "item_count": 1,
        "last_error_code": None,
    }


def cached_alert(snapshot_at):
    return {
        "_id": "sachet:old-alert",
        "title": "Previously retrieved item",
        "description": None,
        "severity": None,
        "urgency": None,
        "event_type": None,
        "affected_location": None,
        "district": None,
        "source_type": "sachet",
        "source_name": "NDMA SACHET",
        "source_url": "https://sachet.ndma.gov.in/alert/old-alert",
        "source_verification_status": "verified",
        "source_published_at": NOW - timedelta(days=1),
        "effective_at": None,
        "last_verified_at": snapshot_at,
        "created_at": snapshot_at,
        "expires_at": None,
        "status": "feed_entry",
        "source_record_id": "old-alert",
        "source_data": {},
        "feed_snapshot_at": snapshot_at,
        "updated_at": snapshot_at,
    }


class SachetRssParsingTests(SimpleTestCase):
    def test_valid_rss_preserves_official_fields_without_mapping_category_to_severity(self):
        parsed = parse_sachet_rss(
            rss_document(rss_item(extra=CAP_FIELDS)),
            now=NOW,
        )
        alert = parsed["alerts"][0]
        self.assertEqual(alert["_id"], "sachet:alert-1")
        self.assertEqual(alert["title"], "Official feed headline")
        self.assertEqual(alert["description"], "Official instructions.")
        self.assertEqual(alert["severity"], "Severe")
        self.assertEqual(alert["urgency"], "Immediate")
        self.assertEqual(alert["event_type"], "Flood")
        self.assertEqual(alert["affected_location"], "Test District")
        self.assertEqual(alert["source_data"]["rss_category"], "Met")
        self.assertNotEqual(alert["severity"], alert["source_data"]["rss_category"])
        self.assertEqual(
            alert["source_url"],
            "https://sachet.ndma.gov.in/alert/alert-1",
        )
        self.assertEqual(parsed["item_count"], 1)

    def test_empty_feed_is_a_successful_empty_snapshot(self):
        parsed = parse_sachet_rss(rss_document(), now=NOW)
        self.assertEqual(parsed["alerts"], [])
        self.assertEqual(parsed["item_count"], 0)

    def test_duplicate_official_guids_are_deduplicated(self):
        parsed = parse_sachet_rss(
            rss_document(
                rss_item(identifier="same-id", title="First"),
                rss_item(identifier="same-id", title="Duplicate"),
            ),
            now=NOW,
        )
        self.assertEqual(len(parsed["alerts"]), 1)
        self.assertEqual(parsed["alerts"][0]["title"], "First")
        self.assertEqual(parsed["duplicate_count"], 1)

    def test_missing_values_are_not_invented_and_expired_entries_are_marked(self):
        item = (
            "<item><guid>missing-fields</guid><title>Headline</title>"
            "<category>Met</category>"
            "<link>https://sachet.ndma.gov.in/alert/1</link>"
            "<cap:expires xmlns:cap='urn:oasis:names:tc:emergency:cap:1.2'>"
            "2026-11-20T00:00:00Z</cap:expires></item>"
        )
        parsed = parse_sachet_rss(rss_document(item), now=NOW)
        alert = parsed["alerts"][0]
        self.assertIsNone(alert["description"])
        self.assertIsNone(alert["severity"])
        self.assertIsNone(alert["urgency"])
        self.assertIsNone(alert["event_type"])
        self.assertIsNone(alert["affected_location"])
        self.assertEqual(alert["status"], "expired")

    def test_invalid_or_unsafe_xml_is_rejected(self):
        with self.assertRaises(SachetFeedError):
            parse_sachet_rss(b"<rss><channel>")
        with self.assertRaises(SachetFeedError) as context:
            parse_sachet_rss(
                b'<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///secret">]>'
                b'<rss version="2.0"><channel>&x;</channel></rss>'
            )
        self.assertEqual(context.exception.code, "unsafe_xml")
        with self.assertRaises(SachetFeedError) as context:
            parse_sachet_rss(
                '<?xml version="1.0"?><!DOCTYPE rss>'
                '<rss version="2.0"><channel/></rss>'.encode("utf-16")
            )
        self.assertEqual(context.exception.code, "unsupported_xml_encoding")


class SachetHttpTests(SimpleTestCase):
    def test_http_200_sends_etag_validator_and_returns_changed_content(self):
        response = FakeResponse(rss_document(rss_item()), etag='"new-etag"')
        with patch("api.services.sachet_feed.urlopen", return_value=response) as opener:
            result = sachet_feed._fetch_sachet_feed(
                '"cached-etag"',
                "Fri, 20 Nov 2026 12:00:00 GMT",
            )
        request = opener.call_args.args[0]
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(request.full_url, SACHET_FEED_URL)
        self.assertEqual(headers["if-none-match"], '"cached-etag"')
        self.assertIn("if-modified-since", headers)
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["etag"], '"new-etag"')

    def test_http_304_is_handled_as_not_modified(self):
        headers = Message()
        headers["ETag"] = '"cached-etag"'
        error = HTTPError(SACHET_FEED_URL, 304, "Not Modified", headers, BytesIO())
        with patch("api.services.sachet_feed.urlopen", side_effect=error):
            result = sachet_feed._fetch_sachet_feed('"cached-etag"')
        self.assertEqual(result["status"], 304)
        self.assertIsNone(result["body"])
        self.assertEqual(result["etag"], '"cached-etag"')

    def test_network_timeout_is_reported_without_real_requests(self):
        with (
            patch(
                "api.services.sachet_feed.urlopen",
                side_effect=TimeoutError("timeout"),
            ),
            self.assertRaises(SachetFeedError) as context,
        ):
            sachet_feed._fetch_sachet_feed()
        self.assertEqual(context.exception.code, "timeout")


class SachetFeedStorageTests(SimpleTestCase):
    def _database(self, snapshot_at=None):
        state = MemoryCollection(
            [cached_state(snapshot_at)] if snapshot_at is not None else []
        )
        alerts = MemoryCollection(
            [cached_alert(snapshot_at)] if snapshot_at is not None else []
        )
        return MemoryDatabase(flood_alerts=alerts, sachet_feed_state=state), alerts, state

    def test_http_200_changed_feed_creates_new_snapshot_without_deleting_old_records(self):
        old_snapshot = NOW - timedelta(minutes=5)
        database, alerts, _state = self._database(old_snapshot)
        with (
            patch(
                "api.services.sachet_feed.check_mongodb_and_prepare_schema",
                return_value=database,
            ),
            patch(
                "api.services.sachet_feed._fetch_sachet_feed",
                return_value={
                    "status": 200,
                    "body": rss_document(rss_item(identifier="new-alert")),
                    "etag": '"new-etag"',
                    "last_modified": "Sat, 21 Nov 2026 12:00:00 GMT",
                },
            ),
        ):
            result = get_sachet_feed(now=NOW)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["refresh_status"], "updated")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["alerts"][0]["source_record_id"], "new-alert")
        self.assertIn("sachet:old-alert", alerts.documents)
        self.assertIn("sachet:new-alert", alerts.documents)

    def test_304_keeps_cached_alerts_and_updates_successful_check_time(self):
        old_snapshot = NOW - timedelta(minutes=5)
        database, alerts, state = self._database(old_snapshot)
        with (
            patch(
                "api.services.sachet_feed.check_mongodb_and_prepare_schema",
                return_value=database,
            ),
            patch(
                "api.services.sachet_feed._fetch_sachet_feed",
                return_value={
                    "status": 304,
                    "body": None,
                    "etag": None,
                    "last_modified": None,
                },
            ) as fetch,
        ):
            result = get_sachet_feed(now=NOW)
        fetch.assert_called_once_with('"old-etag"', "Fri, 20 Nov 2026 12:00:00 GMT")
        self.assertEqual(result["refresh_status"], "not_modified")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["last_successful_update_at"], old_snapshot)
        self.assertEqual(result["last_successful_check_at"], NOW)
        self.assertEqual(len(alerts.update_calls), 0)
        self.assertIn("sachet:old-alert", alerts.documents)
        self.assertIsNone(state.documents["odisha"]["last_error_code"])

    def test_timeout_returns_stale_snapshot_without_mutating_alert_records(self):
        old_snapshot = NOW - timedelta(minutes=5)
        database, alerts, _state = self._database(old_snapshot)
        previous = deepcopy(alerts.documents)
        with (
            patch(
                "api.services.sachet_feed.check_mongodb_and_prepare_schema",
                return_value=database,
            ),
            patch(
                "api.services.sachet_feed._fetch_sachet_feed",
                side_effect=SachetFeedError("timeout"),
            ),
        ):
            result = get_sachet_feed(now=NOW)
        self.assertEqual(result["status"], "stale")
        self.assertEqual(result["refresh_status"], "stale")
        self.assertEqual(result["count"], 1)
        self.assertEqual(alerts.documents, previous)

    def test_invalid_xml_keeps_the_previous_snapshot(self):
        old_snapshot = NOW - timedelta(minutes=5)
        database, alerts, state = self._database(old_snapshot)
        previous = deepcopy(alerts.documents)
        with (
            patch(
                "api.services.sachet_feed.check_mongodb_and_prepare_schema",
                return_value=database,
            ),
            patch(
                "api.services.sachet_feed._fetch_sachet_feed",
                return_value={
                    "status": 200,
                    "body": b"<not-rss>",
                    "etag": '"bad-etag"',
                    "last_modified": None,
                },
            ),
        ):
            result = get_sachet_feed(now=NOW)
        self.assertEqual(result["status"], "stale")
        self.assertEqual(result["count"], 1)
        self.assertEqual(alerts.documents, previous)
        self.assertEqual(state.documents["odisha"]["last_error_code"], "invalid_xml")

    def test_mongodb_unavailable_is_explicit(self):
        with (
            patch(
                "api.services.sachet_feed.check_mongodb_and_prepare_schema",
                side_effect=MongoDBConfigurationError("not configured"),
            ),
            self.assertRaises(SachetFeedDatabaseUnavailable),
        ):
            get_sachet_feed(now=NOW)


class SachetFeedApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_feed_endpoint_returns_entries_with_missing_severity_as_null(self):
        record = parse_sachet_rss(
            rss_document(rss_item(identifier="api-alert")),
            now=NOW,
        )["alerts"][0]
        with patch(
            "api.alert_views.get_sachet_feed",
            return_value={
                "status": "available",
                "refresh_status": "updated",
                "source_name": "NDMA SACHET",
                "source_url": sachet_feed.SACHET_PORTAL_URL,
                "feed_url": SACHET_FEED_URL,
                "last_successful_update_at": NOW,
                "last_successful_check_at": NOW,
                "count": 1,
                "duplicate_count": 0,
                "skipped_count": 0,
                "alerts": [record],
            },
        ):
            response = self.client.get("/api/alerts/sachet/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["alerts"][0]["severity"])
        self.assertEqual(response.data["alerts"][0]["source_type"], "sachet")
        self.assertEqual(response.data["alerts"][0]["status"], "feed_entry")

    def test_database_unavailable_is_reported(self):
        with patch(
            "api.alert_views.get_sachet_feed",
            side_effect=SachetFeedDatabaseUnavailable,
        ):
            response = self.client.get("/api/alerts/sachet/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["error"], "alert_database_unavailable")
