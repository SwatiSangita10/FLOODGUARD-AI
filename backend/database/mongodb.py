"""Reusable, lazily connected MongoDB client and database accessors."""
import atexit
import logging
import os
import re
from threading import Lock
from urllib.parse import unquote, urlsplit

from pymongo import MongoClient
from pymongo.errors import (
    ConfigurationError,
    OperationFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)

from .schema import ensure_collection_indexes

logger = logging.getLogger(__name__)

# Atlas connection strings normally name no database, so the database used by
# FLOODGUARD AI must come from MONGODB_DATABASE. When neither the setting nor
# the URI path names one, fall back to the database the project already uses.
DEFAULT_DATABASE_NAME = "floodguard_ai"

_URI_PATTERN = re.compile(r"mongodb(?:\+srv)?://\S+", re.IGNORECASE)

_client = None
_client_lock = Lock()
_schema_lock = Lock()
_schema_ready = False


class MongoDBConfigurationError(Exception):
    """Raised when required MongoDB environment configuration is absent."""

    def __init__(self, message="", reason="configuration_invalid"):
        super().__init__(message)
        self.reason = reason


class MongoDBUnavailable(PyMongoError):
    """MongoDB could not be used; ``reason`` is a safe, secret-free diagnostic code."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def classify_mongodb_error(exc, stage="connection"):
    """Map a PyMongo failure to a diagnostic code that never includes secrets."""
    if isinstance(exc, MongoDBUnavailable):
        return exc.reason
    if isinstance(exc, OperationFailure):
        if exc.code in {13, 18} or "auth" in str(exc).lower():
            return "authentication_failed"
        if stage == "schema":
            return "index_setup_failed"
        return "operation_not_permitted"
    if isinstance(exc, ServerSelectionTimeoutError):
        return "cannot_reach_atlas"
    if isinstance(exc, ConfigurationError):
        text = str(exc).lower()
        if "dns" in text or "resolution" in text or "srv" in text or "nodename" in text:
            return "dns_resolution_failed"
        return "invalid_uri"
    if stage == "schema":
        return "index_setup_failed"
    return "database_error"


def _redacted(value):
    return _URI_PATTERN.sub("<mongodb-uri>", str(value))[:300]


def configured_database_name():
    configured_name = os.environ.get("MONGODB_DATABASE", "").strip()
    if configured_name:
        return configured_name

    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        return None

    try:
        parsed_uri = urlsplit(uri)
    except ValueError:
        return None

    if parsed_uri.scheme not in {"mongodb", "mongodb+srv"}:
        return None

    database_path = (
        parsed_uri.path[1:]
        if parsed_uri.path.startswith("/")
        else parsed_uri.path
    )
    uri_database_name = unquote(database_path)
    return uri_database_name or DEFAULT_DATABASE_NAME


def get_mongodb_client():
    """Return the process-wide MongoClient, creating it only once."""
    global _client
    if _client is not None:
        return _client

    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        logger.error("MONGODB_URI is not set in this process's environment.")
        raise MongoDBConfigurationError("MONGODB_URI is not configured.", "uri_missing")

    with _client_lock:
        if _client is None:
            try:
                _client = MongoClient(
                    uri,
                    appname="FloodGuard AI",
                    connectTimeoutMS=5_000,
                    serverSelectionTimeoutMS=5_000,
                    socketTimeoutMS=5_000,
                    waitQueueTimeoutMS=5_000,
                    maxPoolSize=20,
                )
            except PyMongoError as exc:
                # mongodb+srv:// URIs are resolved here, so DNS failures surface
                # as ConfigurationError; report them instead of hiding them.
                reason = classify_mongodb_error(exc, "client")
                logger.error(
                    "MongoClient could not be created (%s: %s) -> %s",
                    type(exc).__name__,
                    _redacted(exc),
                    reason,
                )
                raise MongoDBConfigurationError(
                    "MongoDB connection settings are invalid.", reason
                ) from exc

    return _client


def get_mongodb_database():
    database_name = configured_database_name()
    if not database_name:
        logger.error(
            "No MongoDB database name: MONGODB_URI is missing or not a mongodb:// or "
            "mongodb+srv:// URI, and MONGODB_DATABASE is not set."
        )
        raise MongoDBConfigurationError(
            "MongoDB database name could not be determined.",
            "uri_missing" if not os.environ.get("MONGODB_URI", "").strip() else "invalid_uri",
        )
    return get_mongodb_client()[database_name]


def check_mongodb_and_prepare_schema():
    """Ping Atlas, then idempotently prepare empty collections and indexes."""
    global _schema_ready
    database = get_mongodb_database()
    stage = "connection"
    try:
        database.client.admin.command("ping")

        if not _schema_ready:
            with _schema_lock:
                if not _schema_ready:
                    stage = "schema"
                    ensure_collection_indexes(database)
                    _schema_ready = True

        # A collection listing confirms that the configured database is accessible.
        stage = "database_access"
        database.list_collection_names()
    except PyMongoError as exc:
        reason = classify_mongodb_error(exc, stage)
        logger.error(
            "MongoDB check failed during %s (%s: %s) -> %s",
            stage,
            type(exc).__name__,
            _redacted(exc),
            reason,
        )
        raise MongoDBUnavailable(reason) from exc
    return database


def close_mongodb_client():
    """Close the shared pool when this Django process exits."""
    global _client, _schema_ready
    with _client_lock:
        if _client is not None:
            _client.close()
            _client = None
            _schema_ready = False


atexit.register(close_mongodb_client)
