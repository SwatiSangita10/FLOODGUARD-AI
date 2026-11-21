import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from database.mongodb import MongoDBConfigurationError, check_mongodb_and_prepare_schema
from pymongo.errors import PyMongoError

try:
    database = check_mongodb_and_prepare_schema()
    print("atlas_ping=ok")
    print("weather_collection=" + str("weather_records" in database.list_collection_names()))
    print("weather_index=" + str("coordinates_fetched_at" in database["weather_records"].index_information()))
except MongoDBConfigurationError:
    print("atlas_error=MongoDBConfigurationError")
except PyMongoError as error:
    print("atlas_error=" + type(error).__name__)
