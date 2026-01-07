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

    @patch("recipes.ocr_service.ImageRecipeParser")
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

    @patch("recipes.ocr_service.ImageRecipeParser")
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

    @patch("recipes.ocr_service.ImageRecipeParser")
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

    @patch("recipes.ocr_service.ImageRecipeParser")
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

    @patch("recipes.ocr_service.ImageRecipeParser")
    def test_import_image_salvages_multiline_title_blob(self, mock_parser_cls):
        mock_parser = mock_parser_cls.return_value
        # Simulate OCR dumping everything into title and leaving fields empty.
        mock_parser.parse_image.return_value = {
            "title": "Pasta med grönkålspesto\nIngredienser\n1 st Ägg\n2 dl Mjöl\nGör så här\n1. Blanda\n2. Stek",
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
            data={"image": img, "dish_type": "lunch_dinner"},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # Title should be the first line.
        self.assertEqual(data["title"], "Pasta med grönkålspesto")

    @patch("recipes.ocr_service.ImageRecipeParser")
    def test_import_image_parses_source_text_for_instagram(self, mock_parser_cls):
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {"title": "", "description": "", "ingredients": "", "steps": "", "cooking_time": 0, "servings": 4}

        caption = (
            "Asiatisk biffsallad\n"
            "Ingredienser:\n"
            "- 1 st lime\n"
            "- 2 msk soja\n"
            "Gör så här:\n"
            "1. Blanda.\n"
            "2. Servera.\n"
        )

        img = BytesIO(b"fake image data")
        img.name = "test.jpg"

        resp = self.client.post(
            "/api/recipes/import-image/",
            data={"image": img, "source_url": "https://www.instagram.com/reel/ABC/", "source_text": caption},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["title"], "Asiatisk biffsallad")
        self.assertIn("Originalreceptet är från https://www.instagram.com/reel/ABC/", data["description"])
        self.assertIn("1 st lime", data["ingredients"])
        self.assertIn("Blanda.", data["steps"])


    @patch("recipes.ocr_service.ImageRecipeParser")
    def test_import_image_parses_instagram_dressing_sallad_format(self, mock_parser_cls):
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {"title": "", "description": "", "ingredients": "", "steps": "", "cooking_time": 0, "servings": 4}

        caption = (
            "RECEPT på en helt underbar asiatisk biffsallad!\n"
            "Dressing:\n"
            "4 msk japansk soja\n"
            "2 msk sesamolja\n"
            "1-2 tsk sambal oelek\n"
            "Sallad:\n"
            "600 gr flankstek\n"
            "1 litet romansalladshuvud\n"
            "\n"
            "1. Blanda ihop allt till dressingen.\n"
            "2. Lägg upp allt på ett fat.\n"
            "#sallad #recept\n"
        )

        img = BytesIO(b"fake image data")
        img.name = "test.jpg"

        resp = self.client.post(
            "/api/recipes/import-image/",
            data={"image": img, "source_url": "https://www.instagram.com/reel/XYZ/", "source_text": caption},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("Dressing:", data["ingredients"])
        self.assertIn("4 msk japansk soja", data["ingredients"])
        self.assertIn("1-2 tsk sambal oelek", data["ingredients"])
        self.assertIn("Sallad:", data["ingredients"])
        self.assertIn("600 gr flankstek", data["ingredients"])
        self.assertIn("Blanda ihop", data["steps"])

    @patch("recipes.ocr_service.ImageRecipeParser")
    def test_import_image_extracts_hashtags_from_instagram_caption(self, mock_parser_cls):
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {}

        caption = """
Asiatisk biffsallad 🥗
#snabbt #enkelt #middag #nyttigt
Ingredienser:
- Biff
- Sallad
1. Stek biffen.
2. Servera.
"""

        img = BytesIO(b"fake image data")
        img.name = "test.jpg"

        resp = self.client.post(
            "/api/recipes/import-image/",
            data={"image": img, "source_url": "https://www.instagram.com/reel/ABC/", "source_text": caption},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        tags = data["tags"]
        self.assertIn("snabbt", tags)
        self.assertIn("enkelt", tags)
        self.assertIn("middag", tags)
        self.assertIn("nyttigt", tags)

    @patch("recipes.ocr_service.ImageRecipeParser")
    def test_import_image_ignores_parenthetical_notes_in_steps(self, mock_parser_cls):
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {}

        caption = """
Recept på sallad
Ingredienser:
- Biff
Gör så här:
1. Stek biffen.
2. Servera med sallad.
(Funkar även med kyckling, tofu eller halloumi om man vill byta ut biff)
"""

        img = BytesIO(b"fake image data")
        img.name = "test.jpg"

        resp = self.client.post(
            "/api/recipes/import-image/",
            data={"image": img, "source_url": "https://www.instagram.com/reel/XYZ/", "source_text": caption},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        steps = data["steps"]
        # Should have exactly 2 steps, without the parenthetical note.
        self.assertNotIn("Funkar även med kyckling", steps)
        self.assertIn("Stek biffen", steps)
        self.assertIn("Servera med sallad", steps)
