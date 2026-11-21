"""Emergency-resource and alert API tests with MongoDB and providers mocked."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIClient
from bson import ObjectId
from pymongo.errors import ServerSelectionTimeoutError

from api.serializers import AlertWriteSerializer
from api.services import alerts
from api.services.alerts import AlertDatabaseUnavailable
from api.services.reports import ReportDatabaseUnavailable
from api.services.resources import (
    ResourceDatabaseUnavailable,
    _normalize_resource,
    get_resource,
    list_resources,
)
from api.services.weather import WeatherProviderError


RESOURCE_ID = "c2752304-d6e3-48b4-888c-6ca969bf2bc5"
CLIENT_ID = "123e4567-e89b-42d3-a456-426614174000"


def resource_document(*, verification_status="verified"):
    now = datetime.now(timezone.utc)
    return {
        "_id": RESOURCE_ID,
        "name": "District medical centre",
        "category": "hospital",
        "address": "Main Road",
        "district": "Khordha",
        "latitude": 20.3 if verification_status == "verified" else None,
        "longitude": 85.8 if verification_status == "verified" else None,
        "contact_number": "+91 674 1234567",
        "operating_hours": "09:00-17:00",
        "source_name": "Official district directory",
        "source_url": "https://odisha.gov.in/en/contacts/emergency",
        "verification_status": verification_status,
        "last_verified_at": now if verification_status == "verified" else None,
        "created_at": now,
        "updated_at": now,
    }


def alert_document(**changes):
    now = datetime.now(timezone.utc)
    return {
        "_id": "official-alert-1",
        "title": "District flood advisory",
        "description": "Follow local authority instructions.",
        "severity": "Advisory",
        "affected_location": "Khordha",
        "district": "Khordha",
        "source_type": "official",
        "source_name": "OSDMA",
        "source_url": "https://www.osdma.org/emergency-contacts/",
        "source_verification_status": "verified",
        "source_published_at": now,
        "last_verified_at": now,
        "created_at": now,
        "expires_at": now + timedelta(hours=2),
        "status": "active",
        "source_record_id": None,
        "source_data": {},
        "is_read": False,
        **changes,
    }


class EmergencyResourceApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_resource_management_is_not_public(self):
        create = self.client.post("/api/resources/", {}, format="json")
        update = self.client.patch(f"/api/resources/{RESOURCE_ID}/", {}, format="json")
        self.assertIn(create.status_code, (401, 403))
        self.assertIn(update.status_code, (401, 403))

    @patch("api.resource_views.list_resources")
    def test_resource_list_validates_and_forwards_filters(self, list_resources_mock):
        list_resources_mock.return_value = {
            "count": 1,
            "limit": 10,
            "offset": 0,
            "next_offset": None,
            "results": [resource_document()],
        }
        response = self.client.get(
            "/api/resources/?category=hospital&district=Khordha&search=medical"
            "&verification_status=verified&limit=10"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["resource_id"], RESOURCE_ID)
        self.assertEqual(response.data["results"][0]["verification_status"], "verified")
        list_resources_mock.assert_called_once_with(
            category="hospital",
            district="Khordha",
            search="medical",
            verification_status="verified",
            limit=10,
            offset=0,
        )

    def test_invalid_resource_filter_and_missing_database_are_explicit(self):
        response = self.client.get("/api/resources/?category=unknown")
        self.assertEqual(response.status_code, 400)
        with patch(
            "api.resource_views.list_resources",
            side_effect=ResourceDatabaseUnavailable,
        ):
            response = self.client.get("/api/resources/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["error"], "resource_database_unavailable")

    def test_empty_resource_collection_returns_successful_empty_page(self):
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.skip.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.__iter__.return_value = iter([])
        collection = MagicMock()
        collection.count_documents.return_value = 0
        collection.find.return_value = cursor
        with patch("api.services.resources._collection", return_value=collection):
            response = self.client.get("/api/resources/?limit=20")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])
        self.assertIsNone(response.data["next_offset"])

    def test_mongodb_access_failure_is_redacted_in_logs_and_remains_http_503(self):
        failure = ServerSelectionTimeoutError(
            "sensitive MongoDB connection detail"
        )
        with (
            self.assertLogs("api.services.resources", level="ERROR") as captured,
            patch(
                "api.services.resources.check_mongodb_and_prepare_schema",
                side_effect=failure,
            ),
        ):
            response = self.client.get("/api/resources/")
        self.assertEqual(response.status_code, 503)
        self.assertIn("ServerSelectionTimeoutError", captured.output[0])
        self.assertNotIn("sensitive MongoDB connection detail", captured.output[0])

    @patch("api.resource_views.get_resource")
    def test_resource_detail_and_unverified_coordinates(self, get_resource_mock):
        get_resource_mock.return_value = resource_document()
        response = self.client.get(f"/api/resources/{RESOURCE_ID}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["latitude"], 20.3)

        get_resource_mock.return_value = _normalize_resource(
            resource_document(verification_status="unverified")
        )
        response = self.client.get(f"/api/resources/{RESOURCE_ID}/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["latitude"])
        self.assertIsNone(response.data["longitude"])
        self.assertIsNone(response.data["contact_number"])
        self.assertIsNone(response.data["operating_hours"])

    @patch("api.resource_views.list_resource_categories")
    def test_resource_categories_and_missing_directory(self, categories_mock):
        categories_mock.return_value = {
            "categories": [{"value": "hospital", "label": "Hospitals"}],
            "districts": ["Khordha"],
            "total_count": 1,
            "verified_count": 1,
        }
        response = self.client.get("/api/resources/categories/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["districts"], ["Khordha"])
        self.assertEqual(response.data["verified_count"], 1)
        categories_mock.side_effect = ResourceDatabaseUnavailable
        response = self.client.get("/api/resources/categories/")
        self.assertEqual(response.status_code, 503)

    def test_resource_service_uses_all_filters_and_redacts_unverified_coordinates(self):
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.skip.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.__iter__.return_value = iter([
            resource_document(verification_status="unverified")
        ])
        collection = MagicMock()
        collection.count_documents.return_value = 1
        collection.find.return_value = cursor
        with patch("api.services.resources._collection", return_value=collection):
            page = list_resources(
                category="hospital",
                district="Khordha",
                search="Clinic (1)",
                verification_status="unverified",
                limit=10,
                offset=0,
            )
        query = collection.find.call_args.args[0]
        self.assertEqual(query["category"], "hospital")
        self.assertEqual(query["district"]["$options"], "i")
        self.assertIn(r"^Khordha$", query["district"]["$regex"])
        self.assertEqual(query["verification_status"], "unverified")
        self.assertEqual(query["$or"][0]["name"]["$options"], "i")
        self.assertIn(r"Clinic\ \(1\)", query["$or"][0]["name"]["$regex"])
        self.assertIsNone(page["results"][0]["latitude"])
        self.assertEqual(page["results"][0]["contact_number"], "+91 674 1234567")
        self.assertEqual(page["results"][0]["operating_hours"], "09:00-17:00")

    def test_resource_service_reads_existing_mongodb_object_ids(self):
        object_id = ObjectId()
        collection = MagicMock()
        collection.find_one.return_value = {
            **resource_document(),
            "_id": object_id,
        }
        with patch("api.services.resources._collection", return_value=collection):
            resource = get_resource(str(object_id))
        collection.find_one.assert_called_once_with({"_id": object_id})
        self.assertEqual(resource["_id"], object_id)


class EmergencyAlertApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_managed_alert_creation_is_not_public(self):
        response = self.client.post("/api/alerts/", {}, format="json")
        self.assertIn(response.status_code, (401, 403))

    @patch("api.alert_views.list_active_alerts")
    def test_alert_list_returns_real_source_and_read_status(self, list_alerts_mock):
        list_alerts_mock.return_value = {
            "count": 1,
            "unread_count": 1,
            "limit": 20,
            "offset": 0,
            "next_offset": None,
            "results": [alert_document()],
            "sources": {"weather": "not_requested", "verified_reports": "available"},
        }
        response = self.client.get(
            "/api/alerts/?severity=Advisory&district=Khordha&source_type=official"
            f"&client_id={CLIENT_ID}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["severity"], "Advisory")
        self.assertEqual(response.data["results"][0]["source_type"], "official")
        self.assertFalse(response.data["results"][0]["is_read"])
        self.assertEqual(response.data["unread_count"], 1)
        self.assertEqual(list_alerts_mock.call_args.args[0]["severity"], "Advisory")

    @patch("api.alert_views.get_alert")
    def test_alert_detail_and_missing_record(self, get_alert_mock):
        get_alert_mock.return_value = alert_document()
        response = self.client.get(f"/api/alerts/official-alert-1/?client_id={CLIENT_ID}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["alert_id"], "official-alert-1")
        get_alert_mock.return_value = None
        response = self.client.get("/api/alerts/not-found/")
        self.assertEqual(response.status_code, 404)

    @patch("api.alert_views.mark_alert_read")
    def test_mark_read_validation_and_persistence(self, mark_read_mock):
        read_at = datetime.now(timezone.utc)
        mark_read_mock.return_value = {
            "alert_id": "official-alert-1",
            "read_at": read_at,
        }
        response = self.client.post(
            "/api/alerts/mark-read/",
            {"alert_id": "official-alert-1", "client_id": CLIENT_ID},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_read"])
        self.assertEqual(str(mark_read_mock.call_args.args[1]), CLIENT_ID)
        invalid = self.client.post(
            "/api/alerts/mark-read/",
            {"alert_id": "unknown", "client_id": "not-a-uuid"},
            format="json",
        )
        self.assertEqual(invalid.status_code, 400)
        mark_read_mock.side_effect = AlertDatabaseUnavailable
        unavailable = self.client.post(
            "/api/alerts/mark-read/",
            {"alert_id": "official-alert-1", "client_id": CLIENT_ID},
            format="json",
        )
        self.assertEqual(unavailable.status_code, 503)

    @patch("api.alert_views.list_active_alerts", side_effect=AlertDatabaseUnavailable)
    def test_alert_listing_reports_missing_database(self, _list_alerts_mock):
        response = self.client.get("/api/alerts/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["error"], "alert_database_unavailable")

    def test_write_serializer_enforces_official_warning_evidence(self):
        data = {
            "title": "Verified district warning",
            "description": "Use official evacuation instructions.",
            "severity": "Warning",
            "affected_location": "Khordha",
            "source_type": "official",
            "source_name": "OSDMA",
            "source_url": "https://www.osdma.org/emergency-contacts/",
            "source_verification_status": "verified",
            "source_published_at": datetime.now(timezone.utc).isoformat(),
            "last_verified_at": datetime.now(timezone.utc).isoformat(),
        }
        serializer = AlertWriteSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        unsafe = {**data, "source_verification_status": "unverified", "last_verified_at": None}
        serializer = AlertWriteSerializer(data=unsafe)
        self.assertFalse(serializer.is_valid())
        self.assertIn("severity", serializer.errors)
        non_official = {**data, "source_url": "https://example.com/alert"}
        serializer = AlertWriteSerializer(data=non_official)
        self.assertFalse(serializer.is_valid())
        self.assertIn("source_url", serializer.errors)


class AlertSourceAssessmentTests(SimpleTestCase):
    def test_weather_assessments_remain_advisories_not_official_warnings(self):
        now = datetime.now(timezone.utc)
        assessment = {
            "risk_level": "High",
            "score": 64,
            "factors": [{"explanation": "High modelled precipitation."}],
            "weather_freshness": {"provider_timestamp": now.isoformat()},
            "data_completeness": "complete",
        }
        document = alerts._weather_alert_document(
            assessment, 20.3, 85.8, "Bhubaneswar", now
        )
        self.assertEqual(document["severity"], "Advisory")
        self.assertEqual(document["source_type"], "weather")
        self.assertIn("not an official warning", document["description"])

    def test_verified_high_community_report_can_create_warning_with_explicit_caveat(self):
        now = datetime.now(timezone.utc)
        report = {
            "report_id": "report-1",
            "location_name": "Riverside",
            "latitude": 20.3,
            "longitude": 85.8,
            "severity": "high",
            "created_at": now - timedelta(minutes=5),
        }
        collection = MagicMock()
        with patch(
            "api.services.alerts.list_flood_reports",
            return_value={"results": [report], "count": 1},
        ):
            result = alerts._sync_community_alerts(collection, now)
        self.assertEqual(result["status"], "available")
        document = collection.replace_one.call_args.args[1]
        self.assertEqual(document["severity"], "Warning")
        self.assertEqual(document["source_type"], "community")
        self.assertIn("not an official government alert", document["description"])

    def test_missing_verified_reports_are_reported_without_creating_alerts(self):
        now = datetime.now(timezone.utc)
        collection = MagicMock()
        with patch(
            "api.services.alerts.list_flood_reports",
            side_effect=ReportDatabaseUnavailable,
        ):
            result = alerts._sync_community_alerts(collection, now)
        self.assertEqual(result["status"], "unavailable")
        collection.replace_one.assert_not_called()

    def test_nearby_verified_reports_generate_source_labelled_warnings(self):
        now = datetime.now(timezone.utc)
        reports = [
            {
                "report_id": f"report-{index}",
                "location_name": f"Riverside {index}",
                "latitude": 20.3,
                "longitude": 85.8 + index * 0.0001,
                "severity": "moderate",
                "created_at": now - timedelta(minutes=5),
            }
            for index in range(2)
        ]
        collection = MagicMock()
        with patch(
            "api.services.alerts.list_flood_reports",
            return_value={"results": reports, "count": 2},
        ):
            result = alerts._sync_community_alerts(collection, now)
        self.assertEqual(result["status"], "available")
        self.assertEqual(collection.replace_one.call_count, 2)
        for call in collection.replace_one.call_args_list:
            document = call.args[1]
            self.assertEqual(document["severity"], "Warning")
            self.assertEqual(document["source_verification_status"], "verified")

    def test_missing_official_feed_is_not_fabricated_or_promoted(self):
        now = datetime.now(timezone.utc)
        alert_collection = MagicMock()
        alert_collection.count_documents.return_value = 0
        alert_cursor = MagicMock()
        alert_cursor.sort.return_value.skip.return_value.limit.return_value = alert_cursor
        alert_cursor.__iter__.return_value = iter([])
        alert_collection.find.return_value = alert_cursor
        notifications = MagicMock()
        with (
            patch("api.services.alerts._collections", return_value=(alert_collection, notifications)),
            patch("api.services.alerts.list_flood_reports", side_effect=ReportDatabaseUnavailable),
        ):
            page = alerts.list_active_alerts({"limit": 20, "offset": 0})
        self.assertEqual(page["results"], [])
        self.assertEqual(page["sources"]["verified_reports"], "unavailable")
        self.assertEqual(page["sources"]["weather"], "not_requested")

    def test_weather_provider_failure_is_reported_as_unavailable(self):
        with patch(
            "api.services.alerts.fetch_weather",
            side_effect=WeatherProviderError("provider unavailable"),
        ):
            status = alerts._sync_weather_alert(
                MagicMock(), 20.3, 85.8, "Bhubaneswar", datetime.now(timezone.utc)
            )
        self.assertEqual(status, "unavailable")

    def test_weather_advisory_sync_persists_only_advisory_severity(self):
        collection = MagicMock()
        assessment = {
            "assessment_status": "available",
            "risk_level": "Moderate",
            "score": 28,
            "factors": [{"explanation": "Forecast precipitation is elevated."}],
            "weather_freshness": {"provider_timestamp": None},
            "data_completeness": "partial",
        }
        with (
            patch("api.services.alerts.fetch_weather", return_value={"weather": "mocked"}),
            patch("api.services.alerts.assess_weather", return_value=assessment),
        ):
            status = alerts._sync_weather_alert(
                collection, 20.3, 85.8, "Bhubaneswar", datetime.now(timezone.utc)
            )
        self.assertEqual(status, "available")
        document = collection.replace_one.call_args.args[1]
        self.assertEqual(document["severity"], "Advisory")
        self.assertEqual(document["source_type"], "weather")

    def test_mark_read_saves_only_active_alert_receipt(self):
        now = datetime.now(timezone.utc)
        alert_collection = MagicMock()
        alert_collection.find_one.return_value = alert_document(
            _id="official-alert-1",
            expires_at=now + timedelta(hours=1),
        )
        notification_collection = MagicMock()
        receipt = {
            "alert_id": "official-alert-1",
            "client_id": CLIENT_ID,
            "read_at": now,
            "expires_at": now + timedelta(days=90),
        }
        notification_collection.find_one.return_value = receipt
        notification_collection.update_one.return_value = MagicMock()
        with patch(
            "api.services.alerts._collections",
            return_value=(alert_collection, notification_collection),
        ):
            result = alerts.mark_alert_read("official-alert-1", CLIENT_ID)
        self.assertEqual(result["alert_id"], "official-alert-1")
        key = notification_collection.update_one.call_args.args[0]
        self.assertEqual(key, {"client_id": CLIENT_ID, "alert_id": "official-alert-1"})

        alert_collection.find_one.return_value = alert_document(
            _id="official-alert-1",
            expires_at=now - timedelta(hours=1),
        )
        with patch(
            "api.services.alerts._collections",
            return_value=(alert_collection, notification_collection),
        ):
            result = alerts.mark_alert_read("official-alert-1", CLIENT_ID)
        self.assertIsNone(result)
        self.assertEqual(notification_collection.update_one.call_count, 1)

