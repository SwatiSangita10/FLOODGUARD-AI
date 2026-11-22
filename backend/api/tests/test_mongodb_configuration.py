"""Tests for MongoDB environment configuration."""
import os
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIClient
from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError

from database.mongodb import (
    DEFAULT_DATABASE_NAME,
    MongoDBConfigurationError,
    MongoDBUnavailable,
    check_mongodb_and_prepare_schema,
    classify_mongodb_error,
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

    def test_atlas_uri_without_database_uses_the_project_default(self):
        # Regression: Render had MONGODB_URI but neither MONGODB_DATABASE nor a
        # database in the URI path, so the database name resolved to None.
        for uri in (
            "mongodb+srv://user:password@example.mongodb.net/?retryWrites=true",
            "mongodb+srv://user:password@example.mongodb.net",
        ):
            with self.subTest(uri=uri), patch.dict(os.environ, {"MONGODB_URI": uri}, clear=True):
                self.assertEqual(configured_database_name(), DEFAULT_DATABASE_NAME)
                self.assertEqual(DEFAULT_DATABASE_NAME, "floodguard_ai")

    def test_missing_or_non_mongodb_uri_has_no_database_name(self):
        for environment in ({}, {"MONGODB_URI": "https://example.com/db"}):
            with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True):
                self.assertIsNone(configured_database_name())

    def test_missing_uri_is_reported_with_a_reason(self):
        with patch.dict(os.environ, {}, clear=True), patch("database.mongodb._client", None):
            with self.assertRaises(MongoDBConfigurationError) as caught:
                get_mongodb_client()
        self.assertEqual(caught.exception.reason, "uri_missing")

    def test_dns_failure_is_not_reported_as_a_bad_uri(self):
        with (
            patch.dict(os.environ, {"MONGODB_URI": "mongodb+srv://u:p@example.mongodb.net/db"}, clear=True),
            patch("database.mongodb._client", None),
            patch(
                "database.mongodb.MongoClient",
                side_effect=ConfigurationError("The DNS query name does not exist: _mongodb._tcp.example"),
            ),
        ):
            with self.assertRaises(MongoDBConfigurationError) as caught:
                get_mongodb_client()
        self.assertEqual(caught.exception.reason, "dns_resolution_failed")

    def test_error_classification_never_returns_connection_details(self):
        self.assertEqual(
            classify_mongodb_error(ServerSelectionTimeoutError("mongodb+srv://u:secret@host timed out")),
            "cannot_reach_atlas",
        )
        self.assertEqual(
            classify_mongodb_error(OperationFailure("bad auth : Authentication failed.", code=8000)),
            "authentication_failed",
        )
        self.assertEqual(
            classify_mongodb_error(OperationFailure("index build failed", code=67), "schema"),
            "index_setup_failed",
        )

    def test_check_reports_atlas_timeouts_with_a_reason_and_no_secrets(self):
        database = MagicMock()
        database.client.admin.command.side_effect = ServerSelectionTimeoutError("mongodb+srv://u:secret@h")
        with patch("database.mongodb.get_mongodb_database", return_value=database):
            with self.assertRaises(MongoDBUnavailable) as caught:
                check_mongodb_and_prepare_schema()
        self.assertEqual(caught.exception.reason, "cannot_reach_atlas")
        self.assertNotIn("secret", str(caught.exception))

    def test_health_endpoint_returns_reason_codes(self):
        with patch(
            "api.views.check_mongodb_and_prepare_schema",
            side_effect=MongoDBUnavailable("cannot_reach_atlas"),
        ):
            response = APIClient().get("/api/health/database/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["reason"], "cannot_reach_atlas")

        with patch(
            "api.views.check_mongodb_and_prepare_schema",
            side_effect=MongoDBConfigurationError("x", "uri_missing"),
        ):
            response = APIClient().get("/api/health/database/")
        self.assertEqual(response.data["reason"], "uri_missing")

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
