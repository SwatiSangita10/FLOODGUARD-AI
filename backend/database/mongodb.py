"""Reusable, lazily connected MongoDB client and database accessors."""
import atexit
import os
from threading import Lock

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from .schema import ensure_collection_indexes

_client = None
_client_lock = Lock()
_schema_lock = Lock()
_schema_ready = False


class MongoDBConfigurationError(Exception):
    """Raised when required MongoDB environment configuration is absent."""


def configured_database_name():
    return os.environ.get("MONGODB_DATABASE", "").strip() or None


def get_mongodb_client():
    """Return the process-wide MongoClient, creating it only once."""
    global _client
    if _client is not None:
        return _client

    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        raise MongoDBConfigurationError("MONGODB_URI is not configured.")

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
                raise MongoDBConfigurationError("MongoDB connection settings are invalid.") from exc

    return _client


def get_mongodb_database():
    database_name = configured_database_name()
    if not database_name:
        raise MongoDBConfigurationError("MONGODB_DATABASE is not configured.")
    return get_mongodb_client()[database_name]


def check_mongodb_and_prepare_schema():
    """Ping Atlas, then idempotently prepare empty collections and indexes."""
    global _schema_ready
    database = get_mongodb_database()
    database.client.admin.command("ping")

    if not _schema_ready:
        with _schema_lock:
            if not _schema_ready:
                ensure_collection_indexes(database)
                _schema_ready = True

    # A collection listing confirms that the configured database is accessible.
    database.list_collection_names()
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
