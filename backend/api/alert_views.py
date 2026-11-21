"""Public alert reads, anonymous read receipts, and staff-managed official alerts."""
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    AlertDetailQuerySerializer,
    AlertListQuerySerializer,
    AlertReadSerializer,
    AlertWriteSerializer,
    MarkAlertReadSerializer,
)
from .services.alerts import (
    AlertDatabaseUnavailable,
    create_managed_alert,
    get_alert,
    list_active_alerts,
    mark_alert_read,
)
from .services.sachet_feed import (
    SachetFeedDatabaseUnavailable,
    get_sachet_feed,
)


def _database_error():
    return Response(
        {
            "error": "alert_database_unavailable",
            "detail": "Flood alerts are unavailable because MongoDB could not be reached. Use the linked official alert sources.",
        },
        status=503,
    )


class FloodAlertListView(APIView):
    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAdminUser()]

    def get(self, request):
        serializer = AlertListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            page = list_active_alerts(serializer.validated_data)
        except AlertDatabaseUnavailable:
            return _database_error()
        page["results"] = AlertReadSerializer(page["results"], many=True).data
        return Response(page)

    def post(self, request):
        serializer = AlertWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            alert = create_managed_alert(serializer.validated_data)
        except AlertDatabaseUnavailable:
            return _database_error()
        alert["is_read"] = False
        return Response(AlertReadSerializer(alert).data, status=201)


class SachetFeedView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            feed = get_sachet_feed()
        except SachetFeedDatabaseUnavailable:
            return _database_error()
        feed["alerts"] = AlertReadSerializer(feed["alerts"], many=True).data
        return Response(feed)


class FloodAlertDetailView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, alert_id):
        query_serializer = AlertDetailQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        try:
            alert = get_alert(
                alert_id,
                client_id=query_serializer.validated_data.get("client_id"),
            )
        except AlertDatabaseUnavailable:
            return _database_error()
        if alert is None:
            return Response({"detail": "Flood alert not found."}, status=404)
        return Response(AlertReadSerializer(alert).data)


class MarkFloodAlertReadView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = MarkAlertReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            notification = mark_alert_read(
                serializer.validated_data["alert_id"],
                serializer.validated_data["client_id"],
            )
        except AlertDatabaseUnavailable:
            return _database_error()
        if notification is None:
            return Response(
                {"detail": "The active alert was not found; no read receipt was saved."},
                status=404,
            )
        return Response({
            "alert_id": notification["alert_id"],
            "is_read": True,
            "read_at": notification["read_at"],
        })
