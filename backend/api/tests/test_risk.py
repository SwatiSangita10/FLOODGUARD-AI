"""Tests for the preliminary risk indicator, API, and snapshot persistence."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from api.services.risk_assessment import assess_weather
from api.services.risk_storage import RiskStorageError, store_risk_assessment
from api.services.weather import WeatherProviderError
from pymongo.errors import ConnectionFailure


ASSESSMENT_TIME = datetime(2026, 11, 19, 4, 30, tzinfo=timezone.utc)


def weather_data(now=ASSESSMENT_TIME, **changes):
    local_now = now.astimezone(ZoneInfo("Asia/Kolkata"))
    hourly_start = local_now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    hourly_times = [
        (hourly_start + timedelta(hours=offset)).strftime("%Y-%m-%dT%H:%M")
        for offset in range(24)
    ]
    weather = {
        "location": {
            "latitude": 20.2961,
            "longitude": 85.8245,
            "requested_latitude": 20.2961,
            "requested_longitude": 85.8245,
            "timezone": "Asia/Kolkata",
        },
        "current": {
            "time": local_now.strftime("%Y-%m-%dT%H:%M"),
            "values": {"precipitation": 3},
        },
        "hourly": {
            "time": hourly_times,
            "values": {
                "precipitation": [2] * len(hourly_times),
                "precipitation_probability": [40] * len(hourly_times),
            },
        },
        "source": {"name": "Open-Meteo", "attribution_url": "https://open-meteo.com/"},
        "fetched_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    weather.update(changes)
    return weather


class RiskAssessmentServiceTests(SimpleTestCase):
    def test_scores_available_weather_factors_and_explains_the_result(self):
        result = assess_weather(
            weather_data(),
            location_name="Bhubaneswar",
            assessed_at=ASSESSMENT_TIME,
        )
        self.assertEqual(result["score"], 54)
        self.assertEqual(result["risk_level"], "High")
        self.assertEqual(result["assessment_status"], "available")
        self.assertEqual(result["data_completeness"], "complete")
        self.assertEqual(result["location"]["name"], "Bhubaneswar")
        self.assertEqual(result["provider"]["name"], "Open-Meteo")
        self.assertEqual(len(result["factors"]), 4)
        self.assertIn("available factors only", result["explanation"])
        self.assertIn("not scientifically validated", result["limitations"])

    def test_missing_measurements_are_excluded_not_fabricated(self):
        weather = weather_data()
        weather["current"]["values"]["precipitation"] = None
        weather["hourly"]["values"]["precipitation"] = [None] * 24
        weather["hourly"]["values"]["precipitation_probability"] = [None] * 24
        result = assess_weather(weather, assessed_at=ASSESSMENT_TIME)
        self.assertIsNone(result["score"])
        self.assertIsNone(result["risk_level"])
        self.assertEqual(result["assessment_status"], "unavailable")
        self.assertEqual(result["data_completeness"], "unavailable")
        self.assertEqual(result["factors"], [])

    def test_stale_weather_is_not_scored(self):
        weather = weather_data()
        weather["current"]["time"] = "2026-11-19T05:00"
        result = assess_weather(weather, assessed_at=ASSESSMENT_TIME)
        self.assertEqual(result["weather_freshness"]["status"], "stale")
        self.assertEqual(result["assessment_status"], "stale")
        self.assertIsNone(result["score"])
        self.assertEqual(result["factors"], [])

    def test_partial_data_score_uses_only_available_factor_weights(self):
        weather = weather_data()
        weather["current"]["values"]["precipitation"] = None
        weather["hourly"]["values"]["precipitation"] = [None] * 24
        weather["hourly"]["values"]["precipitation_probability"] = [40] * 24
        result = assess_weather(weather, assessed_at=ASSESSMENT_TIME)
        self.assertEqual(result["data_completeness"], "partial")
        self.assertEqual(result["score"], 30)
        self.assertEqual([factor["key"] for factor in result["factors"]], ["precipitation_probability"])


class RiskAssessmentApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_coordinates_are_required_and_validated(self):
        for query in (
            "",
            "?latitude=91&longitude=85",
            "?latitude=20&longitude=-181",
            "?latitude=nan&longitude=85",
            "?latitude=20&longitude=85&timezone=Invalid/Zone",
        ):
            with self.subTest(query=query):
                self.assertEqual(self.client.get(f"/api/risk/assess/{query}").status_code, 400)

    def test_assessment_returns_even_when_snapshot_persistence_fails(self):
        with patch("api.risk_views.fetch_weather", return_value=weather_data()), patch(
            "api.risk_views.store_risk_assessment", side_effect=RiskStorageError
        ):
            response = self.client.get(
                "/api/risk/assess/?latitude=20.2961&longitude=85.8245&location=Bhubaneswar"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["provider"]["name"], "Open-Meteo")
        self.assertEqual(response.data["snapshot"]["status"], "unavailable")
        self.assertEqual(response.data["location"]["name"], "Bhubaneswar")

    def test_provider_failure_is_reported_as_bad_gateway(self):
        with patch("api.risk_views.fetch_weather", side_effect=WeatherProviderError):
            response = self.client.get("/api/risk/assess/?latitude=20&longitude=85")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["error"], "weather_provider_unavailable")

    def test_missing_measurements_are_returned_without_risk_score(self):
        weather = weather_data(datetime.now(timezone.utc))
        weather["current"]["values"]["precipitation"] = None
        weather["hourly"]["values"]["precipitation"] = [None] * 24
        weather["hourly"]["values"]["precipitation_probability"] = [None] * 24
        with patch("api.risk_views.fetch_weather", return_value=weather), patch(
            "api.risk_views.store_risk_assessment", return_value={"status": "stored"}
        ):
            response = self.client.get("/api/risk/assess/?latitude=20&longitude=85")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["score"])
        self.assertEqual(response.data["assessment_status"], "unavailable")


class MemoryRiskCollection:
    def __init__(self):
        self.documents = []

    def find_one(self, query, projection=None, sort=None):
        cutoff = query["assessed_at"]["$gte"]
        return next((
            document for document in self.documents
            if document["location"] == query["location"]
            and document["assessment_fingerprint"] == query["assessment_fingerprint"]
            and document["assessed_at"] >= cutoff
        ), None)

    def insert_one(self, document):
        self.documents.append(deepcopy(document))


class RiskStorageTests(SimpleTestCase):
    def setUp(self):
        self.collection = MemoryRiskCollection()
        self.database = {"risk_assessments": self.collection}
        patcher = patch(
            "api.services.risk_storage.check_mongodb_and_prepare_schema",
            return_value=self.database,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_snapshot_records_inputs_and_deduplicates_same_assessment(self):
        assessment = assess_weather(weather_data(), assessed_at=ASSESSMENT_TIME)
        first = store_risk_assessment(assessment)
        duplicate = store_risk_assessment(assessment)
        self.assertEqual(first["status"], "stored")
        self.assertEqual(duplicate["status"], "recent_snapshot_exists")
        self.assertEqual(len(self.collection.documents), 1)
        document = self.collection.documents[0]
        self.assertEqual(document["risk_score"], assessment["score"])
        self.assertEqual(document["weather_provider"], "Open-Meteo")
        self.assertEqual(document["location"]["coordinates"], [85.8245, 20.2961])
        self.assertEqual(document["assessment_factors"], assessment["factors"])

    def test_database_failure_raises_storage_error(self):
        with patch(
            "api.services.risk_storage.check_mongodb_and_prepare_schema",
            side_effect=ConnectionFailure,
        ):
            with self.assertRaises(RiskStorageError):
                store_risk_assessment(assess_weather(weather_data(), assessed_at=ASSESSMENT_TIME))
