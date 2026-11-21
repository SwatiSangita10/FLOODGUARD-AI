"""MongoDB collection names and the indexes used by planned API queries."""
from pymongo import ASCENDING, DESCENDING, GEOSPHERE

COLLECTIONS = (
    "flood_reports",
    "emergency_resources",
    "risk_assessments",
    "weather_records",
    "route_assessments",
    "flood_alerts",
    "sachet_feed_state",
    "user_notifications",
    "users",
    "chat_history",
)

# Geospatial documents should store `location` as a GeoJSON Point:
# {"type": "Point", "coordinates": [longitude, latitude]}.
# Index creation does not insert any documents.
INDEXES = {
    "flood_reports": (
        ([ ("created_at", DESCENDING) ], {"name": "created_at_desc"}),
        ([ ("status", ASCENDING), ("created_at", DESCENDING) ], {"name": "status_created_at"}),
        ([ ("severity", ASCENDING), ("created_at", DESCENDING) ], {"name": "severity_created_at"}),
        ([ ("location", GEOSPHERE) ], {"name": "location_2dsphere"}),
    ),
    "emergency_resources": (
        ([ ("location", GEOSPHERE) ], {"name": "location_2dsphere"}),
        ([ ("category", ASCENDING), ("district", ASCENDING), ("verification_status", ASCENDING) ], {"name": "category_district_verification"}),
        ([ ("facility_key", ASCENDING) ], {
            "name": "facility_key_unique",
            "unique": True,
            "partialFilterExpression": {"facility_key": {"$type": "string"}},
        }),
        ([ ("source_name", ASCENDING), ("source_record_id", ASCENDING) ], {
            "name": "source_record_unique",
            "unique": True,
            "partialFilterExpression": {"source_record_id": {"$type": "string"}},
        }),
        ([ ("updated_at", DESCENDING) ], {"name": "updated_at_desc"}),
    ),
    "risk_assessments": (
        ([ ("location", ASCENDING), ("assessed_at", DESCENDING) ], {"name": "location_assessed_at"}),
    ),
    "weather_records": (
        ([ ("latitude", ASCENDING), ("longitude", ASCENDING), ("fetched_at", DESCENDING) ], {"name": "coordinates_fetched_at"}),
    ),
    "route_assessments": (
        ([ ("assessed_at", DESCENDING) ], {"name": "assessed_at_desc"}),
    ),
    "flood_alerts": (
        ([ ("status", ASCENDING), ("expires_at", ASCENDING), ("created_at", DESCENDING) ], {"name": "status_expiry_created"}),
        ([ ("severity", ASCENDING), ("created_at", DESCENDING) ], {"name": "severity_created"}),
        ([ ("source_type", ASCENDING), ("source_record_id", ASCENDING) ], {"name": "source_record"}),
    ),
    "sachet_feed_state": (),
    "user_notifications": (
        ([ ("client_id", ASCENDING), ("alert_id", ASCENDING) ], {"name": "client_alert_unique", "unique": True}),
        ([ ("expires_at", ASCENDING) ], {"name": "notification_expiry", "expireAfterSeconds": 0}),
    ),
    "users": (
        ([ ("email", ASCENDING) ], {"name": "email_unique", "unique": True, "sparse": True}),
    ),
    "chat_history": (
        ([ ("conversation_id", ASCENDING), ("created_at", DESCENDING) ], {"name": "conversation_created_at"}),
    ),
}

LEGACY_INDEXES = {
    "flood_reports": ("verification_created_at",),
    "weather_records": ("location_recorded_at",),
}


def ensure_collection_indexes(database):
    """Create the planned empty collections and indexes without sample data."""
    for collection_name in COLLECTIONS:
        collection = database[collection_name]
        desired_names = {options["name"] for _, options in INDEXES[collection_name]}
        existing_names = set(collection.index_information())
        for legacy_name in LEGACY_INDEXES.get(collection_name, ()):
            if legacy_name in existing_names and legacy_name not in desired_names:
                collection.drop_index(legacy_name)
        for keys, options in INDEXES[collection_name]:
            collection.create_index(keys, **options)

    return tuple(database.list_collection_names())
