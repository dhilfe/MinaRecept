import unittest

from recipes.importing import import_recipe_from_html


class LandleyskokIngredientsFallbackTests(unittest.TestCase):
    def test_landleyskok_mvcreate_ingredients_are_extracted(self):
        # Minimal HTML shaped like common "recipe card" plugins (e.g. Mediavine Create),
        # where ingredients are NOT in JSON-LD and NOT in a plain <ul> after an "Ingredienser" heading.
        html = b"""
        <html>
          <head><title>Pulled pork | Landleys k\xc3\xb6k</title></head>
          <body>
            <div class="mv-create-card">
              <div class="mv-create-ingredients">
                <div class="mv-create-ingredients-item">1 kg fl\xc3\xa4skkarr\xc3\xa9</div>
                <div class="mv-create-ingredients-item">1 msk malen spiskummin</div>
              </div>
              <div class="mv-create-instructions">
                <div class="mv-create-instructions-item">G\xc3\xb6r n\xc3\xa5got</div>
              </div>
            </div>
          </body>
        </html>
        """

        data = import_recipe_from_html("https://www.landleyskok.se/recept/test", html)
        self.assertIn("1 kg fläskkarré", data.ingredients)
        self.assertIn("1 msk malen spiskummin", data.ingredients)


