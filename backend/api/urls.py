from django.urls import path

from .views import DatabaseHealthCheckView, HealthCheckView
from .alert_views import (
    FloodAlertDetailView,
    FloodAlertListView,
    MarkFloodAlertReadView,
    SachetFeedView,
)
from .emergency_assistant_views import EmergencyAssistantView
from .report_views import FloodReportDetailView, FloodReportListCreateView
from .resource_views import EmergencyResourceCategoriesView, EmergencyResourceDetailView, EmergencyResourceListView
from .risk_views import RiskAssessmentView
from .safe_route_views import SafeRouteView
from .weather_views import WeatherLocationSearchView, WeatherView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("health/database/", DatabaseHealthCheckView.as_view(), name="database-health-check"),
    path("resources/categories/", EmergencyResourceCategoriesView.as_view(), name="resource-categories"),
    path("resources/", EmergencyResourceListView.as_view(), name="resource-list"),
    path("resources/<str:resource_id>/", EmergencyResourceDetailView.as_view(), name="resource-detail"),
    path("alerts/mark-read/", MarkFloodAlertReadView.as_view(), name="alert-mark-read"),
    path("alerts/sachet/", SachetFeedView.as_view(), name="sachet-feed"),
    path("alerts/", FloodAlertListView.as_view(), name="alert-list"),
    path("alerts/<str:alert_id>/", FloodAlertDetailView.as_view(), name="alert-detail"),
    path("reports/", FloodReportListCreateView.as_view(), name="flood-report-list-create"),
    path("reports/<str:report_id>/", FloodReportDetailView.as_view(), name="flood-report-detail"),
    path("weather/", WeatherView.as_view(), name="weather"),
    path("weather/locations/", WeatherLocationSearchView.as_view(), name="weather-locations"),
    path("risk/assess/", RiskAssessmentView.as_view(), name="risk-assess"),
    path("routes/safe-route/", SafeRouteView.as_view(), name="safe-route"),
    path("assistant/emergency/", EmergencyAssistantView.as_view(), name="emergency-assistant"),
]
