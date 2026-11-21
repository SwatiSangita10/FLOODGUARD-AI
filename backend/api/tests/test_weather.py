"""Weather API and persistence tests with provider and MongoDB calls mocked."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from api.services.weather import (
    CURRENT_VARIABLES,
    DAILY_VARIABLES,
    HOURLY_VARIABLES,
    WeatherProviderError,
    fetch_weather,
)
from api.services.weather_storage import (
    WeatherStorageError,
    store_weather_snapshot,
)
from database.schema import INDEXES
from pymongo.errors import ConnectionFailure


def provider_payload(latitude=20.2961, longitude=85.8245):
    hourly_times = ["2026-11-19T10:00", "2026-11-19T11:00"]
    daily_times = [f"2026-11-{day:02d}" for day in range(19, 26)]
    return {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": "Asia/Kolkata",
        "timezone_abbreviation": "IST",
        "elevation": 45,
        "current_units": {key: ("°C" if "temperature" in key else "mm") for key in CURRENT_VARIABLES},
        "current": {**{key: 1 for key in CURRENT_VARIABLES}, "time": "2026-11-19T10:00", "interval": 900},
        "hourly_units": {key: "mm" for key in HOURLY_VARIABLES},
        "hourly": {"time": hourly_times, **{key: [1, 2] for key in HOURLY_VARIABLES}},
        "daily_units": {key: "mm" for key in DAILY_VARIABLES},
        "daily": {"time": daily_times, **{key: [1] * 7 for key in DAILY_VARIABLES}},
    }


def api_weather(latitude=20.2961, longitude=85.8245):
    return {
        "location": {"latitude": latitude, "longitude": longitude, "timezone": "Asia/Kolkata"},
        "current": {"time": "2026-11-19T10:00", "values": {"temperature_2m": 26}, "units": {"temperature_2m": "°C"}},
        "hourly": {"time": [], "values": {}, "units": {}, "type": "forecast"},
        "daily": {"time": [], "values": {}, "units": {}, "type": "forecast"},
        "source": {"name": "Open-Meteo", "attribution_url": "https://open-meteo.com/"},
        "fetched_at": "2026-11-19T04:30:00Z",
    }


class WeatherApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_valid_weather_for_bhubaneswar_and_another_location(self):
        for latitude, longitude in ((20.2961, 85.8245), (19.8135, 85.8312)):
            with self.subTest(latitude=latitude), patch(
                "api.weather_views.fetch_weather", return_value=api_weather(latitude, longitude)
            ), patch("api.weather_views.store_weather_snapshot", return_value={"status": "stored"}):
                response = self.client.get(
                    f"/api/weather/?latitude={latitude}&longitude={longitude}&timezone=Asia/Kolkata&location_name=Test+City"
                )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["location"]["latitude"], latitude)
            self.assertEqual(response.data["location"]["name"], "Test City")
            self.assertEqual(response.data["snapshot"]["status"], "stored")

    def test_missing_and_invalid_coordinates_are_rejected(self):
        for query in ("", "?latitude=91&longitude=85", "?latitude=20&longitude=-181", "?latitude=abc&longitude=10"):
            with self.subTest(query=query):
                self.assertEqual(self.client.get(f"/api/weather/{query}").status_code, 400)

    def test_weather_service_requests_required_variables_units_and_period(self):
        with patch("api.services.weather._request_json", return_value=provider_payload()) as request:
            result = fetch_weather(20.2961, 85.8245, timezone_name="Asia/Kolkata")
        params = request.call_args.args[1]
        self.assertEqual(params["timezone"], "Asia/Kolkata")
        self.assertEqual(params["temperature_unit"], "celsius")
        self.assertEqual(params["precipitation_unit"], "mm")
        self.assertEqual(params["wind_speed_unit"], "kmh")
        self.assertEqual(params["forecast_hours"], 24)
        self.assertEqual(params["forecast_days"], 7)
        self.assertEqual(set(result["current"]["values"]), set(CURRENT_VARIABLES))
        self.assertEqual(set(result["hourly"]["values"]), set(HOURLY_VARIABLES))
        self.assertEqual(set(result["daily"]["values"]), set(DAILY_VARIABLES))
        self.assertTrue(result["fetched_at"].endswith("Z"))

    def test_invalid_and_empty_location_search(self):
        for query in ("", "q=", "q=x"):
            suffix = "" if not query else f"?{query}"
            response = self.client.get(f"/api/weather/locations/{suffix}")
            self.assertEqual(response.status_code, 400)

    def test_location_search_returns_sanitized_results_and_empty_matches(self):
        location = {"name": "Bhubaneswar", "admin1": "Odisha", "country": "India", "country_code": "IN", "latitude": 20.3, "longitude": 85.8, "timezone": "Asia/Kolkata"}
        with patch("api.weather_views.search_locations", return_value=[location]):
            found = self.client.get("/api/weather/locations/?q=Bhubaneswar")
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.data["results"][0], location)
        with patch("api.weather_views.search_locations", return_value=[]):
            missing = self.client.get("/api/weather/locations/?q=NoSuchTown")
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(missing.data["results"], [])

    def test_provider_timeout_and_malformed_response_are_502(self):
        with patch("api.weather_views.fetch_weather", side_effect=WeatherProviderError):
            response = self.client.get("/api/weather/?latitude=20&longitude=85")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["error"], "weather_provider_unavailable")
        with patch("api.weather_views.search_locations", side_effect=WeatherProviderError):
            response = self.client.get("/api/weather/locations/?q=Bhubaneswar")
        self.assertEqual(response.status_code, 502)

    def test_weather_client_maps_timeout_and_malformed_provider_data(self):
        with patch("api.services.weather.urlopen", side_effect=TimeoutError):
            with self.assertRaises(WeatherProviderError):
                fetch_weather(20.2961, 85.8245)
        with patch("api.services.weather._request_json", return_value={"timezone": "Asia/Kolkata"}):
            with self.assertRaises(WeatherProviderError):
                fetch_weather(20.2961, 85.8245)

    def test_existing_api_and_database_health_endpoints_remain_available(self):
        health = self.client.get("/api/health/")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.data["status"], "ok")
        with patch("api.views.check_mongodb_and_prepare_schema", return_value=SimpleNamespace(name="floodguard_ai")):
            database_health = self.client.get("/api/health/database/")
        self.assertEqual(database_health.status_code, 200)
        self.assertEqual(database_health.data["database"], "floodguard_ai")

    def test_geocoding_service_limits_fields(self):
        from api.services.weather import search_locations

        provider_result = {
            "name": "Bhubaneswar", "admin1": "Odisha", "country": "India", "country_code": "IN",
            "latitude": 20.2961, "longitude": 85.8245, "timezone": "Asia/Kolkata",
            "population": 1000000, "elevation": 45, "provider_id": 123,
        }
        with patch("api.services.weather._request_json", return_value={"results": [provider_result]}) as request:
            result = search_locations("Bhubaneswar")
        self.assertEqual(request.call_args.args[1]["count"], 8)
        self.assertEqual(set(result[0]), {"name", "admin1", "country", "country_code", "latitude", "longitude", "timezone"})
        self.assertNotIn("population", result[0])

    def test_mongo_storage_failure_is_explicit_and_keeps_real_weather_payload(self):
        weather = api_weather()
        with patch("api.weather_views.fetch_weather", return_value=weather), patch(
            "api.weather_views.store_weather_snapshot", side_effect=WeatherStorageError
        ):
            response = self.client.get("/api/weather/?latitude=20&longitude=85")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["error"], "weather_storage_unavailable")
        self.assertIn("weather", response.data)
        self.assertEqual(response.data["snapshot"]["status"], "unavailable")


class MemoryWeatherCollection:
    def __init__(self):
        self.documents = []

    def find_one(self, query, projection=None, sort=None):
        cutoff = query["fetched_at"]["$gte"]
        return next((doc for doc in self.documents if doc["latitude"] == query["latitude"] and doc["longitude"] == query["longitude"] and doc["fetched_at"] >= cutoff), None)

    def insert_one(self, document):
        self.documents.append(deepcopy(document))


class WeatherStorageTests(SimpleTestCase):
    def setUp(self):
        self.collection = MemoryWeatherCollection()
        self.database = {"weather_records": self.collection}
        self.patch_database = patch("api.services.weather_storage.check_mongodb_and_prepare_schema", return_value=self.database)
        self.patch_database.start()
        self.addCleanup(self.patch_database.stop)

    def test_snapshot_is_saved_once_with_location_and_forecasts(self):
        weather = api_weather()
        saved = store_weather_snapshot(weather, location_name="Bhubaneswar")
        duplicate = store_weather_snapshot(weather, location_name="Bhubaneswar")
        self.assertEqual(saved["status"], "stored")
        self.assertEqual(duplicate["status"], "recent_snapshot_exists")
        self.assertEqual(len(self.collection.documents), 1)
        document = self.collection.documents[0]
        self.assertEqual(document["location_name"], "Bhubaneswar")
        self.assertIn("hourly", document)
        self.assertIn("daily", document)

    def test_mongo_failure_raises_storage_error(self):
        with patch("api.services.weather_storage.check_mongodb_and_prepare_schema", side_effect=ConnectionFailure):
            with self.assertRaises(WeatherStorageError):
                store_weather_snapshot(api_weather())

    def test_weather_index_covers_coordinates_and_snapshot_timestamp(self):
        index_keys, index_options = INDEXES["weather_records"][0]
        self.assertEqual(index_options["name"], "coordinates_fetched_at")
        self.assertEqual([field for field, _ in index_keys], ["latitude", "longitude", "fetched_at"])
