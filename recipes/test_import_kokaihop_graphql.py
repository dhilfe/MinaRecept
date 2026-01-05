from unittest.mock import patch

from django.test import SimpleTestCase

from recipes.importing import import_recipe_from_html


class KokaihopGraphQLImportTests(SimpleTestCase):
    @patch("recipes.importing.requests.post")
    def test_kokaihop_graphql_fallback_populates_ingredients_and_steps(self, mock_post):
        # Minimal Kokaihop-like HTML: empty ingredient/step lists, but OG tags exist.
        url = "https://www.kokaihop.se/recept/bacon-och-rodlokssnittar"
        html = b"""
        <html>
          <head>
            <title>Bacon och rodlokssnittar | Kokaihop</title>
            <meta property="og:image" content="https://cdn.example.com/img.jpg" />
          </head>
          <body>
            <div class="ingredients_section"><h3>Ingredienser</h3><ul></ul></div>
            <div class="instructions_section"><h3>G\xc3\xb6r s\xc3\xa5 h\xc3\xa4r:</h3><ol></ol></div>
          </body>
        </html>
        """

        class DummyResp:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "data": {
                        "showRecipe": {
                            "statusCode": 200,
                            "error": None,
                            "data": {
                                "title": "Bacon och rödlökssnittar",
                                "recipeDescription": "Testbeskrivning",
                                "servings": "8",
                                "totalTime": 25,
                                "ingredients": [
                                    {"isHeader": True, "name": "Snittar", "amount": None, "unit": None},
                                    {
                                        "isHeader": False,
                                        "name": "Bacon",
                                        "amount": "200",
                                        "unit": {"name": "g"},
                                    },
                                    {
                                        "isHeader": False,
                                        "name": "Rödlök",
                                        "amount": "1",
                                        "unit": {"name": "st"},
                                    },
                                ],
                                "cookingSteps": ["Stek bacon.", "Toppa brödet."],
                            },
                        }
                    }
                }

        mock_post.return_value = DummyResp()

        data = import_recipe_from_html(url, html)

        self.assertEqual(data.title, "Bacon och rödlökssnittar")
        self.assertEqual(data.servings, 8)
        self.assertEqual(data.cooking_time, 25)
        self.assertEqual(data.image_url, "https://cdn.example.com/img.jpg")

        self.assertIn("200 g Bacon", data.ingredients)
        self.assertIn("1 st Rödlök", data.ingredients)
        self.assertIn("Stek bacon.", data.steps)
        self.assertIn("Toppa brödet.", data.steps)


