from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from pymongo.errors import DuplicateKeyError
from rest_framework.test import APIClient

from api.serializers import (
    FACILITY_RESOURCE_CATEGORIES,
    ResourceReadSerializer,
    ResourceWriteSerializer,
)
from api.services.facility_import import import_official_facilities
from api.services.official_facilities import OFFICIAL_FACILITIES
from api.services.resources import (
    ResourceAlreadyExists,
    _facility_key,
    create_resource,
    list_resources,
)


RESOURCE_ID = "c2752304-d6e3-48b4-888c-6ca969bf2bc5"
NOW = datetime(2026, 11, 21, tzinfo=timezone.utc)


def resource_data(**changes):
    return {
        "name": "Community medical centre",
        "category": "hospital",
        "state": "Odisha",
        "address": "Main Road",
        "district": "Khordha",
        "source_name": "Official district directory",
        "source_url": "https://odisha.gov.in/en/contacts/emergency",
        "verification_status": "unverified",
        **changes,
    }


class MemoryCollection:
    def __init__(self):
        self.documents = {}

    def find_one(self, query):
        for document in self.documents.values():
            matches = True
            for key, expected in query.items():
                actual = document.get(key)
                if isinstance(expected, dict) and "$ne" in expected:
                    if actual == expected["$ne"]:
                        matches = False
                        break
                elif actual != expected:
                    matches = False
                    break
            if matches:
                return deepcopy(document)
        return None

    def insert_one(self, document):
        if self.find_one({"facility_key": document["facility_key"]}):
            raise DuplicateKeyError("duplicate facility key")
        self.documents[document["_id"]] = deepcopy(document)

    def update_one(self, query, update):
        document = self.find_one(query)
        if document is None:
            return SimpleNamespace(matched_count=0)
        document.update(deepcopy(update["$set"]))
        self.documents[document["_id"]] = document
        return SimpleNamespace(matched_count=1)


class FacilityValidationTests(SimpleTestCase):
    def test_requested_physical_categories_are_available_and_helplines_are_separate(self):
        categories = {value for value, _ in FACILITY_RESOURCE_CATEGORIES}
        self.assertTrue({
            "hospital",
            "fire_station",
            "police_station",
            "multipurpose_flood_shelter",
            "multipurpose_cyclone_shelter",
            "relief_centre",
        }.issubset(categories))
        self.assertNotIn("emergency_helpline", categories)

    def test_incomplete_facility_may_omit_contact_and_coordinates(self):
        serializer = ResourceWriteSerializer(data=resource_data(
            category="multipurpose_flood_shelter",
            contact_number="",
        ))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data.get("latitude"))
        self.assertEqual(serializer.validated_data["category"], "multipurpose_flood_shelter")

    def test_verified_facility_requires_a_review_date_and_verified_coordinates(self):
        without_review = ResourceWriteSerializer(data=resource_data(
            verification_status="verified",
        ))
        self.assertFalse(without_review.is_valid())
        self.assertIn("last_verified_at", without_review.errors)

        unverified_coordinates = ResourceWriteSerializer(data=resource_data(
            latitude=20.2,
            longitude=85.8,
        ))
        self.assertFalse(unverified_coordinates.is_valid())
        self.assertIn("coordinates", unverified_coordinates.errors)

    def test_helplines_cannot_be_written_as_physical_facilities(self):
        serializer = ResourceWriteSerializer(data=resource_data(
            category="emergency_helpline",
        ))
        self.assertFalse(serializer.is_valid())
        self.assertIn("category", serializer.errors)

    def test_public_read_serializer_redacts_unverified_contact_and_coordinates(self):
        result = ResourceReadSerializer({
            "_id": RESOURCE_ID,
            **resource_data(
                latitude=None,
                longitude=None,
                contact_number="0674-2391983",
                last_verified_at=None,
                created_at=NOW,
                updated_at=NOW,
                is_active=True,
            ),
        }).data
        self.assertIsNone(result["contact_number"])
        self.assertIsNone(result["latitude"])
        self.assertIsNone(result["longitude"])
        self.assertTrue(result["is_active"])


class FacilityDuplicateTests(SimpleTestCase):
    def test_create_rejects_duplicate_facility_identity(self):
        collection = MemoryCollection()
        data = resource_data()
        with patch("api.services.resources._collection", return_value=collection):
            create_resource(data)
            with self.assertRaises(ResourceAlreadyExists):
                create_resource(data)
        self.assertEqual(len(collection.documents), 1)


class FacilityFilterTests(SimpleTestCase):
    def test_category_district_search_verification_and_active_filters_reach_mongodb(self):
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.skip.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.__iter__.return_value = iter([])
        collection = MagicMock()
        collection.count_documents.return_value = 0
        collection.find.return_value = cursor
        with patch("api.services.resources._collection", return_value=collection):
            list_resources(
                category="police_station",
                district="Puri",
                search="Town",
                verification_status="verified",
                is_active=False,
                limit=10,
                offset=0,
            )
        query = collection.find.call_args.args[0]
        self.assertEqual(query["category"], "police_station")
        self.assertEqual(query["district"]["$regex"], "^Puri$")
        self.assertEqual(query["verification_status"], "verified")
        self.assertEqual(query["last_verified_at"], {"$type": "date"})
        self.assertIs(query["is_active"], False)
        self.assertEqual(query["$or"][0]["name"]["$regex"], "Town")


class FacilityImportTests(SimpleTestCase):
    def test_import_is_repeatable_and_does_not_duplicate_source_records(self):
        collection = MemoryCollection()
        with patch("api.services.facility_import._collection", return_value=collection):
            first = import_official_facilities(apply=True)
            second = import_official_facilities(apply=True)
        self.assertEqual(first["created"], len(OFFICIAL_FACILITIES))
        self.assertEqual(len(collection.documents), len(OFFICIAL_FACILITIES))
        self.assertEqual(second["created"], 0)
        self.assertEqual(second["preserved_verified"], 1)
        self.assertEqual(second["unchanged"], len(OFFICIAL_FACILITIES) - 1)

    def test_incomplete_import_does_not_overwrite_existing_verified_data(self):
        record = next(
            item for item in OFFICIAL_FACILITIES
            if item["verification_status"] == "verified"
        )
        existing = {
            **record,
            "_id": "existing-hospital",
            "facility_key": _facility_key(record),
            "contact_number": "0674-5550000",
            "capacity": 250,
            "created_at": NOW,
            "updated_at": NOW,
            "is_active": False,
        }
        collection = MemoryCollection()
        collection.documents[existing["_id"]] = deepcopy(existing)
        incomplete = {
            **record,
            "contact_number": None,
            "latitude": None,
            "longitude": None,
            "capacity": None,
            "verification_status": "unverified",
            "last_verified_at": None,
        }
        with patch("api.services.facility_import._collection", return_value=collection):
            result = import_official_facilities(apply=True, records=[incomplete])
        saved = collection.documents["existing-hospital"]
        self.assertEqual(result["preserved_verified"], 1)
        self.assertEqual(saved["contact_number"], "0674-5550000")
        self.assertEqual(saved["capacity"], 250)
        self.assertEqual(saved["latitude"], record["latitude"])
        self.assertIs(saved["is_active"], False)
        self.assertEqual(saved["verification_status"], "verified")

    def test_dry_run_does_not_write_records(self):
        collection = MemoryCollection()
        with patch("api.services.facility_import._collection", return_value=collection):
            result = import_official_facilities(apply=False)
        self.assertEqual(result["created"], len(OFFICIAL_FACILITIES))
        self.assertEqual(collection.documents, {})


class FacilityAdminApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_public_users_cannot_create_edit_or_list_deactivated_records(self):
        self.assertIn(
            self.client.post("/api/resources/", {}, format="json").status_code,
            (401, 403),
        )
        self.assertIn(
            self.client.patch(f"/api/resources/{RESOURCE_ID}/", {}, format="json").status_code,
            (401, 403),
        )
        response = self.client.get("/api/resources/?is_active=false")
        self.assertEqual(response.status_code, 403)

    @patch("api.resource_views.list_resources")
    def test_staff_can_query_deactivated_records(self, list_resources_mock):
        list_resources_mock.return_value = {
            "count": 0,
            "limit": 20,
            "offset": 0,
            "next_offset": None,
            "results": [],
        }
        self.client.force_authenticate(
            user=SimpleNamespace(is_staff=True, is_authenticated=True)
        )
        response = self.client.get("/api/resources/?is_active=false")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(list_resources_mock.call_args.kwargs["is_active"])

    @patch("api.services.resources._collection")
    def test_deactivated_facility_is_hidden_from_public_detail(self, collection_mock):
        collection = MagicMock()
        collection.find_one.return_value = {
            "_id": RESOURCE_ID,
            **resource_data(is_active=False),
        }
        collection_mock.return_value = collection
        response = self.client.get(f"/api/resources/{RESOURCE_ID}/")
        self.assertEqual(response.status_code, 404)

    @patch("api.resource_views.update_resource")
    @patch("api.resource_views.get_resource")
    def test_staff_can_deactivate_without_deleting_record(
        self,
        get_resource_mock,
        update_resource_mock,
    ):
        existing = {
            "_id": RESOURCE_ID,
            **resource_data(
                verification_status="verified",
                latitude=20.2,
                longitude=85.8,
                last_verified_at=NOW,
                is_active=True,
                created_at=NOW,
                updated_at=NOW,
            ),
        }
        get_resource_mock.return_value = existing
        update_resource_mock.return_value = {
            **existing,
            "is_active": False,
        }
        self.client.force_authenticate(
            user=SimpleNamespace(is_staff=True, is_authenticated=True)
        )
        response = self.client.patch(
            f"/api/resources/{RESOURCE_ID}/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_active"])
        self.assertEqual(response.data["verification_status"], "verified")

