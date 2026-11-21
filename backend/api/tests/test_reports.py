"""Request-level tests using an isolated in-memory collection."""
from copy import deepcopy
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image
from rest_framework.test import APIClient

from api.services.reports import ReportDatabaseUnavailable


class MemoryCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, key, direction):
        self.documents.sort(key=lambda item: item.get(key), reverse=direction < 0)
        return self

    def skip(self, amount):
        self.documents = self.documents[amount:]
        return self

    def limit(self, amount):
        self.documents = self.documents[:amount]
        return self

    def __iter__(self):
        return iter(self.documents)


class MemoryCollection:
    def __init__(self):
        self.documents = []

    def insert_one(self, document):
        self.documents.append(deepcopy(document))

    def find_one(self, query):
        return next((deepcopy(doc) for doc in self.documents if doc["_id"] == query["_id"]), None)

    def _matching(self, query):
        return [deepcopy(doc) for doc in self.documents if all(doc.get(key) == value for key, value in query.items())]

    def count_documents(self, query):
        return len(self._matching(query))

    def find(self, query):
        return MemoryCursor(self._matching(query))


def valid_payload(**changes):
    return {
        "location_name": "Riverside underpass",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "severity": "moderate",
        "description": "Water is covering the near lane.",
        **changes,
    }


def png_upload(name="client-name.png"):
    image = Image.new("RGB", (3, 3), (0, 40, 90))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class FloodReportApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.collection = MemoryCollection()
        patcher = patch("api.services.reports.get_reports_collection", return_value=self.collection)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_valid_submission_is_created_pending(self):
        response = self.client.post("/api/reports/", valid_payload(), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "pending")
        self.assertTrue(response.data["report_id"])
        self.assertEqual(len(self.collection.documents), 1)
        self.assertEqual(self.collection.documents[0]["location"]["type"], "Point")
        self.assertTrue(response.data["created_at"])

    def test_required_fields_and_field_validation(self):
        self.assertEqual(self.client.post("/api/reports/", {}, format="json").status_code, 400)
        for changes in ({"latitude": 91}, {"longitude": -181}, {"severity": "extreme"}, {"description": "   "}, {"water_level": -1}):
            with self.subTest(changes=changes):
                response = self.client.post("/api/reports/", valid_payload(**changes), format="json")
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.collection.documents, [])

    def test_client_cannot_set_server_controlled_status(self):
        response = self.client.post("/api/reports/", valid_payload(status="verified"), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.collection.documents, [])

    def test_list_filter_pagination_and_detail(self):
        first = self.client.post("/api/reports/", valid_payload(), format="json")
        self.client.post("/api/reports/", valid_payload(severity="critical"), format="json")
        page = self.client.get("/api/reports/?severity=moderate&limit=1&offset=0")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.data["count"], 1)
        self.assertEqual(page.data["results"][0]["report_id"], first.data["report_id"])
        detail = self.client.get(f"/api/reports/{first.data['report_id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["status"], "pending")

    def test_invalid_and_missing_ids(self):
        self.assertEqual(self.client.get("/api/reports/not-a-uuid/").status_code, 400)
        from uuid import uuid4
        self.assertEqual(self.client.get(f"/api/reports/{uuid4()}/").status_code, 404)

    def test_database_failure_returns_503(self):
        with patch("api.services.reports.get_reports_collection", side_effect=ReportDatabaseUnavailable):
            response = self.client.get("/api/reports/")
        self.assertEqual(response.status_code, 503)

    def test_invalid_photo_is_rejected(self):
        bad = SimpleUploadedFile("flood.png", b"not an image", content_type="image/png")
        response = self.client.post("/api/reports/", {**valid_payload(), "photo": bad}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.collection.documents, [])

    def test_valid_photo_uses_storage_and_returns_url(self):
        with patch("api.services.reports.default_storage.save", return_value="reports/generated.png"), patch(
            "api.services.reports.default_storage.url", return_value="/media/reports/generated.png"
        ) as url_mock:
            response = self.client.post("/api/reports/", {**valid_payload(), "photo": png_upload("untrusted-name.png")}, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(url_mock.call_args.args[0], "reports/generated.png")
        self.assertTrue(response.data["photo_url"].endswith("/media/reports/generated.png"))

    def test_oversized_photo_is_rejected(self):
        large = SimpleUploadedFile("large.png", b"x" * (5 * 1024 * 1024 + 1), content_type="image/png")
        response = self.client.post("/api/reports/", {**valid_payload(), "photo": large}, format="multipart")
        self.assertEqual(response.status_code, 400)
