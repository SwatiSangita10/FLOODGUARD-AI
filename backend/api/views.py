from pymongo.errors import PyMongoError
from rest_framework.response import Response
from rest_framework.views import APIView

from database.mongodb import (
    MongoDBConfigurationError,
    check_mongodb_and_prepare_schema,
    configured_database_name,
)


class HealthCheckView(APIView):
    """Report whether the API process is responding."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok", "service": "floodguard-api"})


class DatabaseHealthCheckView(APIView):
    """Check Atlas reachability without returning connection details."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        try:
            database = check_mongodb_and_prepare_schema()
        except MongoDBConfigurationError:
            return Response(
                {
                    "status": "unavailable",
                    "database": configured_database_name(),
                    "message": "MongoDB settings are missing or invalid.",
                },
                status=503,
            )
        except PyMongoError:
            return Response(
                {
                    "status": "unavailable",
                    "database": configured_database_name(),
                    "message": "MongoDB is unreachable or database initialization failed.",
                },
                status=503,
            )

        return Response(
            {
                "status": "ok",
                "database": database.name,
                "message": "MongoDB connection is healthy.",
            }
        )
