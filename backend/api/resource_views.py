"""Read-only public resource directory with staff-managed writes."""
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ResourceListQuerySerializer, ResourceReadSerializer, ResourceWriteSerializer
from .services.resources import (
    ResourceAlreadyExists,
    ResourceDatabaseUnavailable,
    create_resource,
    get_resource,
    is_valid_resource_id,
    list_resource_categories,
    list_resources,
    update_resource,
)


def _database_error():
    return Response(
        {
            "error": "resource_database_unavailable",
            "detail": "The emergency resource directory is unavailable because MongoDB could not be reached.",
        },
        status=503,
    )


class EmergencyResourceListView(APIView):
    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAdminUser()]

    def get(self, request):
        serializer = ResourceListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data
        requested_active_state = filters.pop("is_active", None)
        if requested_active_state == "false" and not getattr(
            request.user,
            "is_staff",
            False,
        ):
            return Response(
                {"detail": "Only staff can list deactivated facility records."},
                status=403,
            )
        if requested_active_state is not None:
            filters["is_active"] = requested_active_state == "true"
        try:
            page = list_resources(**filters)
        except ResourceDatabaseUnavailable:
            return _database_error()
        page["results"] = ResourceReadSerializer(page["results"], many=True).data
        return Response(page)

    def post(self, request):
        serializer = ResourceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            resource = create_resource(serializer.validated_data)
        except ResourceAlreadyExists:
            return Response(
                {
                    "error": "duplicate_emergency_resource",
                    "detail": "A matching facility record already exists.",
                },
                status=409,
            )
        except ResourceDatabaseUnavailable:
            return _database_error()
        return Response(ResourceReadSerializer(resource).data, status=201)


class EmergencyResourceCategoriesView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            result = list_resource_categories()
        except ResourceDatabaseUnavailable:
            return _database_error()
        return Response(result)


class EmergencyResourceDetailView(APIView):
    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAdminUser()]

    def get(self, request, resource_id):
        if not is_valid_resource_id(resource_id):
            return Response({"detail": "Invalid resource ID."}, status=400)
        try:
            resource = get_resource(
                resource_id,
                include_inactive=getattr(request.user, "is_staff", False),
            )
        except ResourceDatabaseUnavailable:
            return _database_error()
        if resource is None:
            return Response({"detail": "Emergency resource not found."}, status=404)
        return Response(ResourceReadSerializer(resource).data)

    def patch(self, request, resource_id):
        if not is_valid_resource_id(resource_id):
            return Response({"detail": "Invalid resource ID."}, status=400)
        try:
            existing = get_resource(resource_id, include_inactive=True)
            if existing is None:
                return Response({"detail": "Emergency resource not found."}, status=404)
            current = {
                key: value
                for key, value in existing.items()
                if key not in ("_id", "created_at", "updated_at", "facility_key")
            }
            updated = {**current, **request.data}
            if updated.get("verification_status") != "verified":
                updated["latitude"] = None
                updated["longitude"] = None
            serializer = ResourceWriteSerializer(data=updated)
            serializer.is_valid(raise_exception=True)
            resource = update_resource(resource_id, serializer.validated_data)
        except ResourceAlreadyExists:
            return Response(
                {
                    "error": "duplicate_emergency_resource",
                    "detail": "A matching facility record already exists.",
                },
                status=409,
            )
        except ResourceDatabaseUnavailable:
            return _database_error()
        if resource is None:
            return Response({"detail": "Emergency resource not found."}, status=404)
        return Response(ResourceReadSerializer(resource).data)
