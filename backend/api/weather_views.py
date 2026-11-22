"""HTTP endpoints for live Open-Meteo data."""
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import WeatherLocationSearchSerializer, WeatherQuerySerializer
from .services.weather import WeatherProviderError, fetch_weather, search_locations
from .services.weather_storage import WeatherStorageError, store_weather_snapshot


class WeatherView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        serializer = WeatherQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data
        try:
            weather = fetch_weather(
                params["latitude"],
                params["longitude"],
                timezone_name=params.get("timezone"),
            )
        except WeatherProviderError as exc:
            return Response(
                {
                    "error": "weather_provider_unavailable",
                    "reason": exc.reason,
                    "detail": "Open-Meteo did not return a valid weather response. Please retry shortly.",
                },
                status=502,
            )

        if params.get("location_name"):
            weather["location"]["name"] = params["location_name"]

        try:
            snapshot = store_weather_snapshot(
                weather, location_name=params.get("location_name")
            )
        except WeatherStorageError:
            return Response(
                {
                    "error": "weather_storage_unavailable",
                    "detail": "Weather was retrieved, but its snapshot could not be saved.",
                    "weather": weather,
                    "snapshot": {"status": "unavailable"},
                },
                status=503,
            )

        weather["snapshot"] = snapshot
        return Response(weather)


class WeatherLocationSearchView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        serializer = WeatherLocationSearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            results = search_locations(serializer.validated_data["q"])
        except WeatherProviderError as exc:
            return Response(
                {
                    "error": "geocoding_provider_unavailable",
                    "reason": exc.reason,
                    "detail": "The location search service is temporarily unavailable.",
                },
                status=502,
            )
        return Response({"results": results})
