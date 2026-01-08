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
    def test_import_image_parses_instagram_du_behover_heading(self, mock_parser_cls):
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {"title": "", "description": "", "ingredients": "", "steps": "", "cooking_time": 0, "servings": 4}

        caption = (
            "Asiatisk biffsallad\n"
            "Du behöver:\n"
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
        self.assertIn("1 st lime", data["ingredients"])
        self.assertIn("2 msk soja", data["ingredients"])
        self.assertIn("Blanda.", data["steps"])


    @patch("recipes.ocr_service.ImageRecipeParser")
    def test_import_image_parses_instagram_ingredients_before_steps_without_heading(self, mock_parser_cls):
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {"title": "", "description": "", "ingredients": "", "steps": "", "cooking_time": 0, "servings": 4}

        caption = (
            "Asiatisk biffsallad\n"
            "1 st lime\n"
            "2 msk soja\n"
            "Gör så här:\n"
            "Blanda.\n"
            "Servera.\n"
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
        self.assertIn("1 st lime", data["ingredients"])
        self.assertIn("2 msk soja", data["ingredients"])
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
    def test_import_image_instagram_caption_missing_ingredients_uses_ocr_fallback_when_api_key_present(
        self, mock_parser_cls
    ):
        mock_parser = mock_parser_cls.return_value
        # Simulate a real OCR-capable environment (avoid mock parser behavior).
        mock_parser.api_key = "test-key"
        mock_parser.parse_image.return_value = {
            "title": "",
            "description": "",
            "ingredients": "1 kg blandfärs\n1 gul lök",
            "steps": "",
            "cooking_time": 0,
            "servings": 4,
        }

        caption_steps_only = (
            "Stek biffarna antingen tills de är genomstekta, eller ge dom bara färg i stekpannan och låt dom sen steka klart I ugnen i 175 grader - dom ska ha en innertemperatur på 70 grader.\n"
            "Stek löken på medelvärme i en klick smör i ca 5 min- direkt i stekpannan där biffarna brynts.\n"
            "Strö över socker och låt steka ytterligare 5 min.\n"
            "Tillsätt buljongen och vattnet. Låt koka 5 minuter.\n"
            "Tillsätt grädde och soja och koka kraftigt i 5 minuter till. Smaka upp med salt och vitpeppar.\n"
            "Servera biffarna i såsen eller med såsen brevid.\n"
        )

        img = BytesIO(b"fake image data")
        img.name = "test.png"

        resp = self.client.post(
            "/api/recipes/import-image/",
            data={
                "image": img,
                "source_url": "https://www.instagram.com/reel/ABC/",
                "source_text": caption_steps_only,
            },
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # Ingredients should come from OCR fallback.
        self.assertIn("blandfärs", data["ingredients"].lower())
        self.assertIn("gul lök", data["ingredients"].lower())

    @patch("recipes.ocr_service.ImageRecipeParser")
    def test_import_image_instagram_caption_identical_ingredients_and_steps_triggers_ocr_fallback(
        self, mock_parser_cls
    ):
        mock_parser = mock_parser_cls.return_value
        mock_parser.api_key = "test-key"
        mock_parser.parse_image.return_value = {
            "title": "",
            "description": "",
            "ingredients": "1 dl mjöl\n2 ägg",
            "steps": "",
            "cooking_time": 0,
            "servings": 4,
        }

        caption_with_duplication = (
            "Testrecept\n"
            "Ingredienser:\n"
            "Stek löken i smör.\n"
            "Tillsätt grädde och soja och låt puttra i 5 minuter.\n"
            "Smaka av med salt och vitpeppar och servera direkt.\n"
            "Gör så här:\n"
            "Stek löken i smör.\n"
            "Tillsätt grädde och soja och låt puttra i 5 minuter.\n"
            "Smaka av med salt och vitpeppar och servera direkt.\n"
        )

        img = BytesIO(b"fake image data")
        img.name = "test.jpg"

        resp = self.client.post(
            "/api/recipes/import-image/",
            data={
                "image": img,
                "source_url": "https://www.instagram.com/reel/DUP/",
                "source_text": caption_with_duplication,
            },
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # Ingredients should come from OCR fallback (not duplicated steps).
        self.assertIn("mjöl", data["ingredients"].lower())
        self.assertIn("ägg", data["ingredients"].lower())
        # Steps should remain from caption.
        self.assertIn("Stek löken", data["steps"])

    @patch("recipes.ocr_service.ImageRecipeParser")
    def test_import_image_instagram_caption_identical_ingredients_and_steps_does_not_blank_ingredients_when_ocr_empty(
        self, mock_parser_cls
    ):
        mock_parser = mock_parser_cls.return_value
        mock_parser.api_key = "test-key"
        mock_parser.parse_image.return_value = {
            "title": "",
            "description": "",
            "ingredients": "",
            "steps": "",
            "cooking_time": 0,
            "servings": 4,
        }

        caption_with_duplication = (
            "Testrecept\n"
            "Ingredienser:\n"
            "Stek löken i smör och tillsätt grädde och soja och låt puttra i 5 minuter.\n"
            "Smaka av med salt och vitpeppar och servera direkt.\n"
            "Gör så här:\n"
            "Stek löken i smör och tillsätt grädde och soja och låt puttra i 5 minuter.\n"
            "Smaka av med salt och vitpeppar och servera direkt.\n"
        )

        img = BytesIO(b"fake image data")
        img.name = "test.jpg"

        resp = self.client.post(
            "/api/recipes/import-image/",
            data={
                "image": img,
                "source_url": "https://www.instagram.com/reel/DUP2/",
                "source_text": caption_with_duplication,
            },
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # Prefer empty ingredients over duplicating steps when OCR cannot find ingredients.
        self.assertEqual(data["ingredients"].strip(), "")
        self.assertIn("Stek löken", data["steps"])

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

    @patch("recipes.ocr_service.ImageRecipeParser")
    def test_import_image_handles_step_heading_variations(self, mock_parser_cls):
        """Test variations of 'Gör så här' heading: typos, spacing, parentheses."""
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {}

        # Test "För så här" (typo), "Gör såhär" (no space), and heading with parentheses
        captions = [
            """
Ingredienser:
- Ägg
För så här:
1. Rör ihop
2. Stek
""",
            """
Ingredienser:
- Mjöl
Gör såhär:
1. Blanda
2. Grädda
""",
            """
Ingredienser:
- Pasta
Gör så här (tar typ 5 minuter):
1. Koka pasta
2. Häll av vattnet
""",
            """
Ingredienser:
- Sallad
Så här gör du:
1. Hacka grönsaker
2. Blanda
""",
        ]

        for caption in captions:
            with self.subTest(caption=caption[:50]):
                img = BytesIO(b"fake image data")
                img.name = "test.jpg"

                resp = self.client.post(
                    "/api/recipes/import-image/",
                    data={"image": img, "source_url": "https://www.instagram.com/reel/ABC/", "source_text": caption},
                    format="multipart",
                )

                self.assertEqual(resp.status_code, 201)
                data = resp.json()
                self.assertTrue(data["ingredients"], f"Should have ingredients for: {caption[:30]}")
                self.assertTrue(data["steps"], f"Should have steps for: {caption[:30]}")

    @patch("recipes.ocr_service.ImageRecipeParser")
    def test_import_image_parses_recept_format_with_long_sentences(self, mock_parser_cls):
        """Test 'Recept:' heading followed by short ingredient lines and long sentence steps."""
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {}

        caption = """
Recept:
2 dl mjöl
3 ägg
1 dl mjölk
Blanda mjöl och ägg i en skål. Tillsätt mjölken gradvis medan du vispar. Stek pannkakor i smör tills de är gyllene på båda sidor.
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
        
        # Ingredients should have the short lines
        self.assertIn("mjöl", data["ingredients"])
        self.assertIn("ägg", data["ingredients"])
        
        # Steps should have the long sentences
        self.assertIn("Blanda mjöl och ägg", data["steps"])
        self.assertIn("Stek pannkakor", data["steps"])

    @patch("recipes.ocr_service.ImageRecipeParser")
    def test_import_image_parses_subsections_with_long_steps(self, mock_parser_cls):
        """Test multiple subsections (Biffar:, Sås:) followed by long step sentences."""
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {}

        caption = """
PANNBIFF I LÖKSÅS

Biffar:
500 g färs
0,5 dl grädde
1 ägg
1 msk lökpulver
0,5 tsk malen svartpeppar
1 tsk salt
0,25 tsk kryddpeppar

Sås:
2 gula lökar, skivade
1 tärning köttbuljong
3 dl vatten
2 dl grädde
1 tsk socker
1 tsk kinesisk soja
Salt & malen vitpeppar

Stek biffarna antingen tills de är genomstekta, eller ge dom bara färg i stekpannan och låt dom sen steka klart I ugnen i 175 grader - dom ska ha en innertemperatur på 70 grader.
Stek löken på medelvärme i en klick smör i ca 5 min- direkt i stekpannan där biffarna brynts.
Strö över socker och låt steka ytterligare 5 min.
Tillsätt buljongen och vattnet. Låt koka 5 minuter.
Tillsätt grädde och soja och koka kraftigt i 5 minuter till. Smaka upp med salt och vitpeppar.
Servera biffarna i såsen eller med såsen brevid.
"""

        img = BytesIO(b"fake image data")
        img.name = "test.jpg"

        resp = self.client.post(
            "/api/recipes/import-image/",
            data={"image": img, "source_url": "https://www.instagram.com/reel/DSCVeYhDI8y/", "source_text": caption},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        
        # Ingredients should have both Biffar and Sås sections with short lines
        self.assertIn("Biffar:", data["ingredients"])
        self.assertIn("500 g färs", data["ingredients"])
        self.assertIn("Sås:", data["ingredients"])
        self.assertIn("2 gula lökar", data["ingredients"])
        
        # Long sentences should be steps, not ingredients
        self.assertIn("Stek biffarna", data["steps"])
        self.assertIn("Stek löken på medelvärme", data["steps"])
        self.assertIn("Servera biffarna", data["steps"])
        
        # Make sure steps don't contain \n escapes (should be split by lines)
        self.assertNotIn("\\n", data["steps"])


    @patch("recipes.ocr_service.ImageRecipeParser")
    def test_import_image_does_not_put_numbered_steps_in_ingredients_without_heading(self, mock_parser_cls):
        """If caption has numbered steps but no explicit 'Gör så här' heading, steps must not be duplicated into ingredients."""
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {}

        caption = """
Tomatsallad
Ingredienser:
2 tomater
1 msk olivolja
1. Skär tomaterna i klyftor.
2. Blanda med olivolja och salt.
"""

        img = BytesIO(b"fake image data")
        img.name = "test.jpg"

        resp = self.client.post(
            "/api/recipes/import-image/",
            data={"image": img, "source_url": "https://www.instagram.com/reel/NOHEADING/", "source_text": caption},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()

        self.assertIn("2 tomater", data["ingredients"])
        self.assertIn("1 msk olivolja", data["ingredients"])
        self.assertNotIn("Skär tomaterna", data["ingredients"])
        self.assertNotIn("Blanda med olivolja", data["ingredients"])

        self.assertIn("Skär tomaterna", data["steps"])
        self.assertIn("Blanda med olivolja", data["steps"])


    @patch("recipes.ocr_service.ImageRecipeParser")
    def test_import_image_instagram_emoji_prefixed_steps_are_not_added_to_ingredients(self, mock_parser_cls):
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {}

        caption = """
PANNBIFF I LÖKSÅS

Biffar:
500 g färs
1 ägg

Sås:
2 gula lökar
2 dl grädde

👉 Stek biffarna i stekpannan.
➡️ Tillsätt grädde och låt puttra.
"""

        img = BytesIO(b"fake image data")
        img.name = "test.jpg"

        resp = self.client.post(
            "/api/recipes/import-image/",
            data={"image": img, "source_url": "https://www.instagram.com/reel/EMOJI/", "source_text": caption},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("500 g färs", data["ingredients"])
        self.assertIn("2 gula lökar", data["ingredients"])
        self.assertNotIn("Stek biffarna", data["ingredients"])
        self.assertNotIn("Tillsätt grädde", data["ingredients"])
        self.assertIn("Stek biffarna", data["steps"])
        self.assertIn("Tillsätt grädde", data["steps"])


    @patch("recipes.ocr_service.ImageRecipeParser")
    def test_import_image_instagram_steps_not_starting_with_verb_are_not_added_to_ingredients(self, mock_parser_cls):
        mock_parser = mock_parser_cls.return_value
        mock_parser.parse_image.return_value = {}

        caption = """
PANNBIFF I LÖKSÅS

Biffar:
500 g färs
1 ägg

Sås:
2 gula lökar
2 dl grädde

I en stekpanna på medelvärme bryner du biffarna och låter dem gå klart i 175 grader i ugnen.
Sedan blandar du ner grädde och soja och låter allt puttra i 5 minuter.
"""

        img = BytesIO(b"fake image data")
        img.name = "test.jpg"

        resp = self.client.post(
            "/api/recipes/import-image/",
            data={"image": img, "source_url": "https://www.instagram.com/reel/NOVERB/", "source_text": caption},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("500 g färs", data["ingredients"])
        self.assertIn("2 dl grädde", data["ingredients"])
        self.assertNotIn("I en stekpanna", data["ingredients"])
        self.assertNotIn("Sedan blandar du", data["ingredients"])
        self.assertIn("I en stekpanna", data["steps"])
        self.assertIn("Sedan blandar du", data["steps"])

