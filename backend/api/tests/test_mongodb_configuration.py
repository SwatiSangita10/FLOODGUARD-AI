"""Tests for MongoDB environment configuration."""
import os
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIClient
from pymongo.errors import ServerSelectionTimeoutError

from database.mongodb import (
    configured_database_name,
    get_mongodb_client,
    get_mongodb_database,
)


class MongoDBConfigurationTests(SimpleTestCase):
    def test_explicit_database_setting_takes_precedence_over_uri_path(self):
        with patch.dict(
            os.environ,
            {
                "MONGODB_DATABASE": "configured_database",
                "MONGODB_URI": "mongodb://user:password@localhost/uri_database",
            },
            clear=True,
        ):
            self.assertEqual(configured_database_name(), "configured_database")

    def test_uri_database_is_used_when_explicit_setting_is_empty(self):
        with patch.dict(
            os.environ,
            {
                "MONGODB_DATABASE": " ",
                "MONGODB_URI": "mongodb+srv://user:password@example.mongodb.net/floodguard%5Fai?retryWrites=true",
            },
            clear=True,
        ):
            self.assertEqual(configured_database_name(), "floodguard_ai")

    def test_uri_without_database_requires_a_separate_setting(self):
        with patch.dict(
            os.environ,
            {"MONGODB_URI": "mongodb+srv://user:password@example.mongodb.net/?retryWrites=true"},
            clear=True,
        ):
            self.assertIsNone(configured_database_name())

    def test_client_uses_the_process_mongodb_uri_and_existing_timeouts(self):
        uri = "mongodb://user:password@localhost/floodguard_ai"
        with (
            patch.dict(os.environ, {"MONGODB_URI": uri}, clear=True),
            patch("database.mongodb._client", None),
            patch("database.mongodb.MongoClient") as mongo_client,
        ):
            client = get_mongodb_client()

        self.assertIs(client, mongo_client.return_value)
        mongo_client.assert_called_once_with(
            uri,
            appname="FloodGuard AI",
            connectTimeoutMS=5_000,
            serverSelectionTimeoutMS=5_000,
            socketTimeoutMS=5_000,
            waitQueueTimeoutMS=5_000,
            maxPoolSize=20,
        )

    def test_database_selection_uses_the_uri_database(self):
        uri = "mongodb://user:password@localhost/floodguard_ai"
        with (
            patch.dict(os.environ, {"MONGODB_URI": uri}, clear=True),
            patch("database.mongodb._client", None),
            patch("database.mongodb.MongoClient") as mongo_client,
        ):
            database = get_mongodb_database()

        self.assertIs(database, mongo_client.return_value.__getitem__.return_value)
        mongo_client.return_value.__getitem__.assert_called_once_with("floodguard_ai")

    def test_database_health_reports_uri_database_on_connection_failure(self):
        uri = "mongodb+srv://user:password@example.mongodb.net/floodguard_ai"
        with patch.dict(os.environ, {"MONGODB_URI": uri}, clear=True), patch(
            "api.views.check_mongodb_and_prepare_schema",
            side_effect=ServerSelectionTimeoutError("private connection detail"),
        ):
            response = APIClient().get("/api/health/database/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["database"], "floodguard_ai")
        self.assertNotIn("private connection detail", str(response.data))
