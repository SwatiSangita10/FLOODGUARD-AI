"""HTTP endpoint for OSRM route planning and available-data risk assessment."""
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import SafeRouteRequestSerializer
from .services.safe_routes import (
    RouteProviderError,
    RouteStorageError,
    assess_safe_route,
    store_route_assessment,
)


class SafeRouteView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = SafeRouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            assessment = assess_safe_route(
                serializer.validated_data["origin"],
                serializer.validated_data["destination"],
            )
        except RouteProviderError:
            return Response(
                {
                    "error": "routing_provider_unavailable",
                    "detail": "OSRM could not provide a valid driving route. Please retry shortly.",
                },
                status=502,
            )

        try:
            assessment["history"] = store_route_assessment(assessment)
        except RouteStorageError:
            assessment["history"] = {
                "status": "unavailable",
                "detail": "The route was assessed, but its history could not be saved to MongoDB.",
            }
        return Response(assessment)
