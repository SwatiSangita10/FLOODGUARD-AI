"""Safe route API and assessment tests with routing, weather, and MongoDB mocked."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from api.services.reports import ReportDatabaseUnavailable
from api.services.safe_routes import (
    RouteProviderError,
    RouteStorageError,
    classify_route_risk,
    store_route_assessment,
)
from api.services.weather import WeatherProviderError
from pymongo.errors import ConnectionFailure


ORIGIN = {"latitude": 20.2961, "longitude": 85.8245}
DESTINATION = {"latitude": 20.32, "longitude": 85.85}
def osrm_payload():
    return {
        "code": "Ok",
        "routes": [
            {
                "distance": 5400,
                "duration": 900,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [85.8245, 20.2961],
                        [85.837, 20.308],
                        [85.85, 20.32],
                    ],
                },
            },
            {
                "distance": 6200,
                "duration": 1080,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [85.8245, 20.2961],
                        [85.84, 20.31],
                        [85.85, 20.32],
                    ],
                },
            },
        ],
    }


def weather_data(precipitation=0):
    now = datetime.now(timezone.utc)
    return {
        "location": {
            "latitude": ORIGIN["latitude"],
            "longitude": ORIGIN["longitude"],
            "requested_latitude": ORIGIN["latitude"],
            "requested_longitude": ORIGIN["longitude"],
            "timezone": "UTC",
        },
        "current": {
            "time": now.isoformat(timespec="minutes"),
            "values": {"precipitation": precipitation},
        },
        "hourly": {
            "time": [
                (now + timedelta(hours=offset)).isoformat(timespec="minutes")
                for offset in range(1, 25)
            ],
            "values": {
                "precipitation": [0] * 24,
                "precipitation_probability": [0] * 24,
            },
        },
        "source": {"name": "Open-Meteo", "attribution_url": "https://open-meteo.com/"},
        "fetched_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def verified_report():
    return {
        "report_id": "verified-report-1",
        "latitude": 20.308,
        "longitude": 85.837,
        "severity": "moderate",
        "description": "Verified waterlogging report.",
        "created_at": datetime.now(timezone.utc),
    }


class SafeRouteApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def request_payload(self):
        return {"origin": ORIGIN, "destination": DESTINATION}

    def route_patches(self, *, reports=None, report_error=None, weather_error=None):
        def report_page(coordinates, status=None, limit=500):
            if report_error:
                raise report_error
            if status != "verified":
                return {"count": 0, "with_coordinates": 0, "without_coordinates": 0, "results": []}
            page_reports = [dict(report, _id=report["report_id"]) for report in (reports or [])]
            return {
                "count": len(page_reports),
                "with_coordinates": len(page_reports),
                "without_coordinates": 0,
                "results": page_reports,
            }

        patches = [
            patch("api.services.safe_routes._request_routing_json", return_value=osrm_payload()),
            patch(
                "api.services.safe_routes.list_flood_reports_near_route",
                side_effect=report_page,
            ),
            patch(
                "api.services.safe_routes.fetch_weather",
                side_effect=weather_error,
                return_value=weather_data(),
            ),
            patch(
                "api.safe_route_views.store_route_assessment",
                return_value={"status": "stored"},
            ),
            patch(
                "api.services.safe_routes.get_sachet_feed",
                return_value={
                    "status": "none",
                    "alerts": [],
                    "alerts_without_coordinates": 0,
                    "count": 0,
                    "last_successful_check_at": None,
                },
            ),
        ]
        return patches

    def test_valid_request_returns_osrm_route_weather_and_verified_reports(self):
        patches = self.route_patches(reports=[verified_report()])
        with patches[0], patches[1], patches[2] as weather, patches[3], patches[4]:
            response = self.client.post(
                "/api/routes/safe-route/", self.request_payload(), format="json"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["routing"]["provider"], "OSRM public routing service")
        self.assertEqual(response.data["route"]["distance_m"], 5400)
        self.assertEqual(response.data["distance_km"], 5.4)
        self.assertEqual(response.data["risk_classification"]["level"], "High")
        self.assertEqual(len(response.data["flood_observations"]["observations"]), 1)
        self.assertEqual(len(response.data["alternatives"]), 1)
        self.assertEqual(weather.call_count, 3)
        self.assertEqual(response.data["history"]["status"], "stored")

    def test_invalid_or_identical_coordinates_are_rejected(self):
        invalid_payloads = (
            {},
            {"origin": {"latitude": 91, "longitude": 85}, "destination": DESTINATION},
            {"origin": ORIGIN, "destination": {"latitude": 20, "longitude": 181}},
            {"origin": ORIGIN, "destination": ORIGIN},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.client.post(
                    "/api/routes/safe-route/", payload, format="json"
                )
                self.assertEqual(response.status_code, 400)
        nan_response = self.client.post(
            "/api/routes/safe-route/",
            '{"origin":{"latitude":NaN,"longitude":85},"destination":{"latitude":20.32,"longitude":85.85}}',
            content_type="application/json",
        )
        self.assertEqual(nan_response.status_code, 400)

    def test_routing_provider_failure_returns_502(self):
        with patch(
            "api.services.safe_routes._request_routing_json",
            side_effect=RouteProviderError,
        ):
            response = self.client.post(
                "/api/routes/safe-route/", self.request_payload(), format="json"
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["error"], "routing_provider_unavailable")

    def test_missing_flood_and_weather_data_are_unknown_not_safe(self):
        patches = self.route_patches(
            report_error=ReportDatabaseUnavailable,
            weather_error=WeatherProviderError,
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            response = self.client.post(
                "/api/routes/safe-route/", self.request_payload(), format="json"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["flood_observations"]["status"], "unavailable")
        self.assertEqual(response.data["risk_classification"]["level"], "Unknown")
        self.assertIn("insufficient", response.data["risk_classification"]["explanation"])
        self.assertTrue(all(
            item["assessment_status"] == "unavailable"
            for item in response.data["weather_assessments"]
        ))

    def test_route_history_database_failure_is_explicit(self):
        patches = self.route_patches()
        with patches[0], patches[1], patches[2], patch(
            "api.safe_route_views.store_route_assessment",
            side_effect=RouteStorageError,
        ), patches[4]:
            response = self.client.post(
                "/api/routes/safe-route/", self.request_payload(), format="json"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["history"]["status"], "unavailable")
        self.assertIn("could not be saved", response.data["history"]["detail"])


class RouteRiskClassificationTests(SimpleTestCase):
    def test_pending_report_maps_to_moderate_warning(self):
        risk = classify_route_risk(
            [{"assessment_status": "available", "risk_level": "Low"}],
            {
                "status": "available",
                "observations": [{"report_id": "pending", "verification_status": "pending"}],
            },
        )
        self.assertEqual(risk["level"], "Moderate")
        self.assertIn("pending citizen flood report", risk["explanation"])

    def test_geographically_matched_sachet_alert_maps_to_high_warning(self):
        risk = classify_route_risk(
            [{"assessment_status": "available", "risk_level": "Low"}],
            {"status": "none", "observations": []},
            {"alerts": [{"alert_id": "sachet:1"}]},
        )
        self.assertEqual(risk["level"], "High")
        self.assertIn("SACHET alert", risk["explanation"])

    def test_verified_report_takes_priority_over_low_weather(self):
        risk = classify_route_risk(
            [{"assessment_status": "available", "risk_level": "Low"}],
            {"status": "available", "observations": [{"report_id": "report"}]},
        )
        self.assertEqual(risk["level"], "High")
        self.assertIn("verified flood report", risk["explanation"])

    def test_weather_categories_are_mapped_conservatively(self):
        cases = (
            ([{"assessment_status": "available", "risk_level": "High"}], "High"),
            ([{"assessment_status": "available", "risk_level": "Moderate"}], "Moderate"),
            ([{"assessment_status": "available", "risk_level": "Low"}], "Low"),
            ([{"assessment_status": "unavailable", "risk_level": None}], "Unknown"),
        )
        for assessments, expected in cases:
            with self.subTest(expected=expected):
                result = classify_route_risk(
                    assessments, {"status": "none", "observations": []}
                )
                self.assertEqual(result["level"], expected)

    def test_low_weather_is_unknown_when_report_source_cannot_be_checked(self):
        risk = classify_route_risk(
            [{"assessment_status": "available", "risk_level": "Low"}],
            {"status": "unavailable", "observations": []},
        )
        self.assertEqual(risk["level"], "Unknown")

    def test_low_weather_is_unknown_when_verified_report_search_is_truncated(self):
        risk = classify_route_risk(
            [{"assessment_status": "available", "risk_level": "Low"}],
            {"status": "partial", "observations": []},
        )
        self.assertEqual(risk["level"], "Unknown")


class RouteAssessmentStorageTests(SimpleTestCase):
    def test_mongodb_failure_raises_storage_error(self):
        assessment = {
            "origin": ORIGIN,
            "destination": DESTINATION,
            "assessed_at": "2026-11-20T05:00:00Z",
            "route": {"distance_m": 5400, "duration_s": 900},
            "risk_classification": {"level": "Unknown", "explanation": "No data."},
            "risk_factors": [],
            "routing": {"provider": "OSRM"},
            "weather_provider": {"name": "Open-Meteo"},
            "flood_observations": {"status": "unavailable"},
        }
        with patch(
            "api.services.safe_routes.check_mongodb_and_prepare_schema",
            side_effect=ConnectionFailure,
        ):
            with self.assertRaises(RouteStorageError):
                store_route_assessment(assessment)
