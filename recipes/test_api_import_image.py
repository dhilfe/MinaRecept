from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient


class ImportImageAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="imguser", password="password")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch("recipes.api_views.ImageRecipeParser")
    def test_import_image_creates_recipe(self, mock_parser_cls):
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {
            "title": "OCR Test",
            "description": "Beskrivning",
            "ingredients": "1 st Ägg\n2 dl Mjöl",
            "steps": "1. Gör\n2. Klar",
            "cooking_time": 12,
            "servings": 3,
        }

        img = BytesIO(b"fake image data")
        img.name = "test.jpg"

        resp = self.client.post(
            "/api/recipes/import-image/",
            data={"image": img, "dish_type": "dessert"},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["title"], "OCR Test")
        self.assertEqual(data["dish_type"], "dessert")

    def test_import_image_missing_image_returns_400(self):
        resp = self.client.post("/api/recipes/import-image/", data={}, format="multipart")
        self.assertEqual(resp.status_code, 400)

    @patch("recipes.api_views.ImageRecipeParser")
    def test_import_image_empty_ocr_still_creates_placeholder_recipe(self, mock_parser_cls):
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {
            "title": "",
            "description": "",
            "ingredients": "",
            "steps": "",
            "cooking_time": 0,
            "servings": 0,
        }

        img = BytesIO(b"fake image data")
        img.name = "test.jpg"

        resp = self.client.post(
            "/api/recipes/import-image/",
            data={"image": img, "title": "Min titel"},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["title"], "Min titel")

    @patch("recipes.api_views.ImageRecipeParser")
    def test_import_image_prefers_provided_title_when_ocr_is_mock(self, mock_parser_cls):
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {
            "title": "Mockat Recept från Bild",
            "description": "",
            "ingredients": "1 st Ägg",
            "steps": "1. Test",
            "cooking_time": 10,
            "servings": 2,
        }

        img = BytesIO(b"fake image data")
        img.name = "test.jpg"

        resp = self.client.post(
            "/api/recipes/import-image/",
            data={"image": img, "title": "Bacon och rödlökssnittar", "dish_type": "appetizer"},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["title"], "Bacon och rödlökssnittar")
        self.assertEqual(data["dish_type"], "appetizer")

    @patch("recipes.api_views.ImageRecipeParser")
    def test_import_image_truncates_title_to_200(self, mock_parser_cls):
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {
            "title": "A" * 500,
            "description": "",
            "ingredients": "",
            "steps": "",
            "cooking_time": 0,
            "servings": 4,
        }

        img = BytesIO(b"fake image data")
        img.name = "test.jpg"

        resp = self.client.post(
            "/api/recipes/import-image/",
            data={"image": img, "dish_type": "dessert"},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(len(data["title"]), 200)


