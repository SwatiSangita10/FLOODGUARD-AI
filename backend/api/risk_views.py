"""HTTP endpoint for preliminary, explainable weather-based risk assessment."""
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RiskAssessmentQuerySerializer
from .services.risk_assessment import assess_weather
from .services.risk_storage import RiskStorageError, store_risk_assessment
from .services.weather import WeatherProviderError, fetch_weather


class RiskAssessmentView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        serializer = RiskAssessmentQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data
        try:
            weather = fetch_weather(
                params["latitude"],
                params["longitude"],
                timezone_name=params.get("timezone"),
            )
        except WeatherProviderError:
            return Response(
                {
                    "error": "weather_provider_unavailable",
                    "detail": "Open-Meteo did not return valid weather data. Please retry shortly.",
                },
                status=502,
            )

        if params.get("location"):
            weather["location"]["name"] = params["location"]

        assessment = assess_weather(weather, location_name=params.get("location"))
        try:
            assessment["snapshot"] = store_risk_assessment(assessment)
        except RiskStorageError:
            assessment["snapshot"] = {"status": "unavailable"}
        return Response(assessment)
