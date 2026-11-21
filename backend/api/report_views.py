"""HTTP endpoints for citizen-submitted flood reports."""
import re
from uuid import UUID

from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    FloodReportCreateSerializer,
    FloodReportListQuerySerializer,
    FloodReportReadSerializer,
)
from .services.reports import (
    ReportDatabaseUnavailable,
    ReportPhotoStorageUnavailable,
    create_flood_report,
    get_flood_report,
    list_flood_reports,
)


def _database_error():
    return Response(
        {"detail": "Flood reports are temporarily unavailable."}, status=503
    )


class FloodReportListCreateView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request):
        query_serializer = FloodReportListQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        params = query_serializer.validated_data
        try:
            page = list_flood_reports(**params)
        except ReportDatabaseUnavailable:
            return _database_error()

        page["next_offset"] = (
            page["offset"] + len(page["results"])
            if page["offset"] + len(page["results"]) < page["count"]
            else None
        )
        page["results"] = FloodReportReadSerializer(
            page["results"], many=True, context={"request": request}
        ).data
        return Response(page)

    def post(self, request):
        serializer = FloodReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            report = create_flood_report(serializer.validated_data)
        except ReportPhotoStorageUnavailable:
            return Response({"detail": "Photo upload failed."}, status=503)
        except ReportDatabaseUnavailable:
            return _database_error()

        return Response(
            FloodReportReadSerializer(report, context={"request": request}).data,
            status=201,
        )


class FloodReportDetailView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, report_id):
        try:
            UUID(report_id)
        except (ValueError, TypeError, AttributeError):
            return Response({"detail": "Invalid report ID."}, status=400)

        try:
            report = get_flood_report(report_id)
        except ReportDatabaseUnavailable:
            return _database_error()
        if report is None:
            return Response({"detail": "Flood report not found."}, status=404)
        return Response(
            FloodReportReadSerializer(report, context={"request": request}).data
        )
