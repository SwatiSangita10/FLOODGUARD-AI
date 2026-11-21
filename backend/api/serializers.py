"""Validation and JSON representations for citizen flood reports."""
import warnings
import math
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
PHOTO_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
SEVERITY_CHOICES = ("low", "moderate", "high", "critical")
STATUS_CHOICES = ("pending", "verified", "rejected")
RESOURCE_CATEGORIES = (
    ("hospital", "Hospitals and medical facilities"),
    ("fire_station", "Fire stations"),
    ("police_station", "Police stations"),
    ("multipurpose_flood_shelter", "Multipurpose flood shelters"),
    ("multipurpose_cyclone_shelter", "Multipurpose cyclone shelters"),
    ("relief_centre", "Relief centres"),
    # Keep prior values readable for existing MongoDB records.
    ("shelter", "Emergency shelters and relief centres"),
    ("fire_rescue", "Fire and rescue services"),
    ("police", "Police stations"),
    ("disaster_management", "Disaster management offices"),
    ("ambulance", "Ambulance services"),
    ("emergency_helpline", "Emergency helpline (legacy contact, not a facility)"),
)
FACILITY_RESOURCE_CATEGORIES = tuple(
    item for item in RESOURCE_CATEGORIES if item[0] != "emergency_helpline"
)
RESOURCE_VERIFICATION_CHOICES = ("verified", "unverified")
ALERT_SEVERITY_CHOICES = ("Information", "Advisory", "Warning", "Emergency")
ALERT_SOURCE_CHOICES = ("official", "manual", "weather", "community", "sachet")
ALERT_SOURCE_VERIFICATION_CHOICES = ("verified", "unverified", "not_applicable")
OFFICIAL_SOURCE_HOSTS = (
    "osdma.org",
    "srcodisha.nic.in",
    "odisha.gov.in",
    "sachet.ndma.gov.in",
    "ndma.gov.in",
)


class FloodPhotoField(serializers.FileField):
    """Validate the image contents and ignore the client-provided filename."""

    def to_internal_value(self, data):
        upload = super().to_internal_value(data)
        if upload.size > MAX_PHOTO_BYTES:
            raise serializers.ValidationError("Photo must be 5 MB or smaller.")

        image_format = None
        try:
            upload.seek(0)
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(upload) as image:
                    image_format = image.format
                    if image.width * image.height > MAX_IMAGE_PIXELS:
                        raise serializers.ValidationError("Photo dimensions are too large.")
                    image.verify()
        except serializers.ValidationError:
            raise
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            OSError,
            UnidentifiedImageError,
            ValueError,
        ) as exc:
            raise serializers.ValidationError(
                "Upload a valid JPEG, PNG, or WebP image."
            ) from exc
        finally:
            upload.seek(0)

        if image_format not in PHOTO_FORMATS:
            raise serializers.ValidationError("Only JPEG, PNG, and WebP photos are supported.")

        upload.validated_image_format = image_format
        return upload


class FloodReportCreateSerializer(serializers.Serializer):
    location_name = serializers.CharField(max_length=160, trim_whitespace=True)
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    severity = serializers.ChoiceField(choices=SEVERITY_CHOICES)
    description = serializers.CharField(max_length=2000, trim_whitespace=True)
    water_level = serializers.FloatField(required=False, allow_null=True, min_value=0)
    photo = FloodPhotoField(required=False, allow_null=True)

    def to_internal_value(self, data):
        protected_fields = {"status", "report_id", "_id", "created_at", "photo_url"}
        supplied_fields = protected_fields.intersection(data.keys())
        if supplied_fields:
            errors = {
                field: "This field is assigned by the server and cannot be submitted."
                for field in sorted(supplied_fields)
            }
            raise serializers.ValidationError(errors)
        return super().to_internal_value(data)


class FloodReportListQuerySerializer(serializers.Serializer):
    severity = serializers.ChoiceField(choices=SEVERITY_CHOICES, required=False)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=False)
    limit = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)
    offset = serializers.IntegerField(required=False, default=0, min_value=0)


class FloodReportReadSerializer(serializers.Serializer):
    report_id = serializers.CharField(source="_id")
    location_name = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    severity = serializers.ChoiceField(choices=SEVERITY_CHOICES)
    description = serializers.CharField()
    water_level = serializers.FloatField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    created_at = serializers.DateTimeField()
    photo_url = serializers.SerializerMethodField()

    def get_photo_url(self, report):
        photo_url = report.get("photo_url")
        request = self.context.get("request")
        if photo_url and request:
            return request.build_absolute_uri(photo_url)
        return photo_url


class WeatherQuerySerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    location_name = serializers.CharField(required=False, max_length=160, trim_whitespace=True)
    timezone = serializers.CharField(required=False, max_length=64, trim_whitespace=True)

    def validate_latitude(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError("Enter a finite latitude.")
        return value

    def validate_longitude(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError("Enter a finite longitude.")
        return value

    def validate_timezone(self, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError("Use a valid IANA time zone.")
        return value


class RiskAssessmentQuerySerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    location = serializers.CharField(required=False, max_length=160, trim_whitespace=True)
    timezone = serializers.CharField(required=False, max_length=64, trim_whitespace=True)

    def validate_latitude(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError("Enter a finite latitude.")
        return value

    def validate_longitude(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError("Enter a finite longitude.")
        return value

    def validate_timezone(self, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError("Use a valid IANA time zone.")
        return value


class RouteCoordinateSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)

    def validate_latitude(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError("Enter a finite latitude.")
        return value

    def validate_longitude(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError("Enter a finite longitude.")
        return value


class SafeRouteRequestSerializer(serializers.Serializer):
    origin = RouteCoordinateSerializer()
    destination = RouteCoordinateSerializer()

    def validate(self, attrs):
        origin = attrs["origin"]
        destination = attrs["destination"]
        if (
            origin["latitude"] == destination["latitude"]
            and origin["longitude"] == destination["longitude"]
        ):
            raise serializers.ValidationError(
                {"destination": "Choose a destination different from the origin."}
            )
        return attrs


class WeatherLocationSearchSerializer(serializers.Serializer):
    q = serializers.CharField(min_length=2, max_length=100, trim_whitespace=True)


class StringOnlyCharField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            raise serializers.ValidationError("A string is required.")
        return super().to_internal_value(data)


class EmergencyAssistantHistoryItemSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=("user", "assistant"))
    content = StringOnlyCharField(
        min_length=1,
        max_length=1000,
        trim_whitespace=True,
        allow_blank=False,
    )


class EmergencyAssistantMessageSerializer(serializers.Serializer):
    message = StringOnlyCharField(
        min_length=1,
        max_length=1000,
        trim_whitespace=True,
        allow_blank=False,
    )
    history = EmergencyAssistantHistoryItemSerializer(
        many=True,
        required=False,
        default=list,
        max_length=10,
    )

    def validate_history(self, history):
        if sum(len(item["content"]) for item in history) > 5000:
            raise serializers.ValidationError("Conversation context is too long.")
        return history


class ResourceListQuerySerializer(serializers.Serializer):
    category = serializers.ChoiceField(
        choices=[item[0] for item in FACILITY_RESOURCE_CATEGORIES],
        required=False,
    )
    district = serializers.CharField(required=False, max_length=100, trim_whitespace=True)
    search = serializers.CharField(required=False, max_length=100, trim_whitespace=True)
    verification_status = serializers.ChoiceField(
        choices=RESOURCE_VERIFICATION_CHOICES,
        required=False,
    )
    is_active = serializers.ChoiceField(
        choices=("true", "false"),
        required=False,
    )
    limit = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)
    offset = serializers.IntegerField(required=False, default=0, min_value=0)


class ResourceWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=180, trim_whitespace=True)
    category = serializers.ChoiceField(
        choices=[item[0] for item in FACILITY_RESOURCE_CATEGORIES]
    )
    state = serializers.CharField(required=False, allow_blank=True, max_length=100, trim_whitespace=True)
    address = serializers.CharField(required=False, allow_blank=True, max_length=300, trim_whitespace=True)
    district = serializers.CharField(required=False, allow_blank=True, max_length=100, trim_whitespace=True)
    block = serializers.CharField(required=False, allow_blank=True, max_length=100, trim_whitespace=True)
    gram_panchayat = serializers.CharField(required=False, allow_blank=True, max_length=120, trim_whitespace=True)
    village = serializers.CharField(required=False, allow_blank=True, max_length=120, trim_whitespace=True)
    latitude = serializers.FloatField(required=False, allow_null=True, min_value=-90, max_value=90)
    longitude = serializers.FloatField(required=False, allow_null=True, min_value=-180, max_value=180)
    contact_number = serializers.CharField(required=False, allow_blank=True, max_length=32, trim_whitespace=True)
    operating_hours = serializers.CharField(required=False, allow_blank=True, max_length=200, trim_whitespace=True)
    capacity = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    source_name = serializers.CharField(max_length=160, trim_whitespace=True)
    source_url = serializers.URLField(max_length=500)
    source_record_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=200,
        trim_whitespace=True,
    )
    verification_status = serializers.ChoiceField(
        choices=RESOURCE_VERIFICATION_CHOICES,
        default="unverified",
    )
    last_verified_at = serializers.DateTimeField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_latitude(self, value):
        if value is not None and not math.isfinite(value):
            raise serializers.ValidationError("Enter a finite latitude.")
        return value

    def validate_longitude(self, value):
        if value is not None and not math.isfinite(value):
            raise serializers.ValidationError("Enter a finite longitude.")
        return value

    def validate_latitude(self, value):
        if value is not None and not math.isfinite(value):
            raise serializers.ValidationError("Enter a finite latitude.")
        return value

    def validate_longitude(self, value):
        if value is not None and not math.isfinite(value):
            raise serializers.ValidationError("Enter a finite longitude.")
        return value

    def validate_contact_number(self, value):
        if value:
            digits = re.sub(r"\D", "", value)
            if (
                not re.fullmatch(r"\+?[0-9][0-9\s().-]{5,24}", value)
                or not 7 <= len(digits) <= 15
            ):
                raise serializers.ValidationError("Enter a valid telephone number.")
        return value

    def validate(self, attrs):
        latitude = attrs.get("latitude")
        longitude = attrs.get("longitude")
        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError(
                {"coordinates": "Latitude and longitude must be supplied together."}
            )
        if latitude is not None and attrs.get("verification_status") != "verified":
            raise serializers.ValidationError(
                {"coordinates": "Only verified resource locations may publish coordinates."}
            )
        if (
            attrs.get("verification_status") == "verified"
            and not attrs.get("last_verified_at")
            and not self.partial
        ):
            raise serializers.ValidationError(
                {"last_verified_at": "A verified resource needs a verification timestamp."}
            )
        if attrs.get("last_verified_at") and attrs["last_verified_at"] > datetime.now(timezone.utc):
            raise serializers.ValidationError(
                {"last_verified_at": "Verification time cannot be in the future."}
            )
        return attrs


class ResourceReadSerializer(serializers.Serializer):
    resource_id = serializers.CharField(source="_id")
    name = serializers.CharField()
    category = serializers.ChoiceField(choices=[item[0] for item in RESOURCE_CATEGORIES])
    state = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    address = serializers.CharField(allow_null=True, allow_blank=True)
    district = serializers.CharField(allow_null=True, allow_blank=True)
    block = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    gram_panchayat = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    village = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    latitude = serializers.FloatField(allow_null=True)
    longitude = serializers.FloatField(allow_null=True)
    contact_number = serializers.SerializerMethodField()
    operating_hours = serializers.SerializerMethodField()
    capacity = serializers.IntegerField(allow_null=True, required=False)
    source_name = serializers.CharField()
    source_url = serializers.URLField()
    source_record_id = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    verification_status = serializers.ChoiceField(choices=RESOURCE_VERIFICATION_CHOICES)
    last_verified_at = serializers.DateTimeField(allow_null=True)
    is_active = serializers.BooleanField(default=True)
    created_at = serializers.DateTimeField(allow_null=True, required=False)
    updated_at = serializers.DateTimeField(allow_null=True, required=False)
    last_updated_at = serializers.DateTimeField(
        source="updated_at",
        allow_null=True,
        required=False,
    )

    def get_contact_number(self, resource):
        if resource.get("verification_status") != "verified":
            return None
        return resource.get("contact_number")

    def get_operating_hours(self, resource):
        if resource.get("verification_status") != "verified":
            return None
        return resource.get("operating_hours")


class AlertListQuerySerializer(serializers.Serializer):
    severity = serializers.ChoiceField(choices=ALERT_SEVERITY_CHOICES, required=False)
    district = serializers.CharField(required=False, max_length=100, trim_whitespace=True)
    search = serializers.CharField(required=False, max_length=100, trim_whitespace=True)
    source_type = serializers.ChoiceField(
        choices=("official", "manual", "weather", "community"),
        required=False,
    )
    verification_status = serializers.ChoiceField(
        choices=ALERT_SOURCE_VERIFICATION_CHOICES,
        required=False,
    )
    latitude = serializers.FloatField(required=False, min_value=-90, max_value=90)
    longitude = serializers.FloatField(required=False, min_value=-180, max_value=180)
    location_name = serializers.CharField(required=False, max_length=160, trim_whitespace=True)
    client_id = serializers.UUIDField(required=False)
    limit = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)
    offset = serializers.IntegerField(required=False, default=0, min_value=0)

    def validate(self, attrs):
        if ("latitude" in attrs) != ("longitude" in attrs):
            raise serializers.ValidationError(
                {"coordinates": "Latitude and longitude must be supplied together."}
            )
        for coordinate in ("latitude", "longitude"):
            if coordinate in attrs and not math.isfinite(attrs[coordinate]):
                raise serializers.ValidationError({coordinate: "Enter a finite coordinate."})
        return attrs


class AlertWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=180, trim_whitespace=True)
    description = serializers.CharField(max_length=2000, trim_whitespace=True)
    severity = serializers.ChoiceField(choices=ALERT_SEVERITY_CHOICES)
    affected_location = serializers.CharField(max_length=180, trim_whitespace=True)
    district = serializers.CharField(required=False, allow_blank=True, max_length=100, trim_whitespace=True)
    source_type = serializers.ChoiceField(choices=("official", "manual"))
    source_name = serializers.CharField(max_length=160, trim_whitespace=True)
    source_url = serializers.URLField(max_length=500)
    source_verification_status = serializers.ChoiceField(
        choices=("verified", "unverified"),
        default="unverified",
    )
    source_published_at = serializers.DateTimeField(required=False, allow_null=True)
    last_verified_at = serializers.DateTimeField(required=False, allow_null=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs):
        hostname = (urlsplit(attrs["source_url"]).hostname or "").lower()
        official_source = any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in OFFICIAL_SOURCE_HOSTS
        )
        if attrs["source_type"] == "official" and not official_source:
            raise serializers.ValidationError(
                {"source_url": "Use a URL from an approved official government source."}
            )
        if attrs["severity"] in ("Warning", "Emergency") and (
            attrs["source_verification_status"] != "verified"
        ):
            raise serializers.ValidationError(
                {"severity": "Warnings require a verified source."}
            )
        if (
            attrs["source_verification_status"] == "verified"
            and not attrs.get("last_verified_at")
        ):
            raise serializers.ValidationError(
                {"last_verified_at": "A verified alert needs a verification timestamp."}
            )
        if attrs["severity"] == "Emergency" and (
            attrs["source_type"] != "official"
            or not attrs.get("source_published_at")
            or not attrs.get("last_verified_at")
        ):
            raise serializers.ValidationError(
                {"severity": "Emergency alerts require a verified official source and publication time."}
            )
        if attrs["source_type"] == "official" and (
            attrs["source_verification_status"] == "verified"
            and not attrs.get("last_verified_at")
        ):
            raise serializers.ValidationError(
                {"last_verified_at": "A verified official alert needs a verification timestamp."}
            )
        expires_at = attrs.get("expires_at")
        if expires_at and expires_at <= datetime.now(timezone.utc):
            raise serializers.ValidationError(
                {"expires_at": "Expiry must be in the future."}
            )
        now = datetime.now(timezone.utc)
        for field in ("source_published_at", "last_verified_at"):
            if attrs.get(field) and attrs[field] > now:
                raise serializers.ValidationError(
                    {field: "Source timestamps cannot be in the future."}
                )
        return attrs


class AlertReadSerializer(serializers.Serializer):
    alert_id = serializers.CharField(source="_id")
    title = serializers.CharField(allow_null=True, allow_blank=True)
    description = serializers.CharField(allow_null=True, allow_blank=True)
    severity = serializers.CharField(allow_null=True, allow_blank=True)
    urgency = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    event_type = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    affected_location = serializers.CharField(allow_null=True, allow_blank=True)
    district = serializers.CharField(allow_null=True, allow_blank=True)
    source_type = serializers.ChoiceField(choices=ALERT_SOURCE_CHOICES)
    source_name = serializers.CharField()
    source_url = serializers.URLField(allow_null=True, allow_blank=True)
    source_verification_status = serializers.ChoiceField(
        choices=ALERT_SOURCE_VERIFICATION_CHOICES
    )
    source_published_at = serializers.DateTimeField(allow_null=True)
    last_verified_at = serializers.DateTimeField(allow_null=True)
    effective_at = serializers.DateTimeField(allow_null=True, required=False)
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField(allow_null=True)
    status = serializers.ChoiceField(
        choices=("active", "resolved", "expired", "feed_entry")
    )
    source_record_id = serializers.CharField(allow_null=True, allow_blank=True)
    source_data = serializers.JSONField(required=False)
    is_read = serializers.BooleanField(default=False)


class MarkAlertReadSerializer(serializers.Serializer):
    alert_id = serializers.CharField(max_length=200, trim_whitespace=True)
    client_id = serializers.UUIDField()


class AlertDetailQuerySerializer(serializers.Serializer):
    client_id = serializers.UUIDField(required=False)
