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

    def test_landleyskok_does_not_pick_nav_menu_as_ingredients(self):
        # Simulate the exact failure mode: a nav/menu contains "ingrediens" and a nearby <ul>.
        # Real recipe section is inside #recept-content further down.
        html = b"""
        <html>
          <head><title>S\xc3\xa5 enkelt \xc3\xa4r det att g\xc3\xb6ra pulled pork | Landleys k\xc3\xb6k</title></head>
          <body>
            <nav>
              <p>Receptgeneratorn 2.0</p>
              <ul>
                <li>Receptgeneratorn 2.0</li>
                <li>Hitta recept efter ingrediens</li>
                <li>Om Landleys k\xc3\xb6k</li>
                <li>Mina sparade recept</li>
              </ul>
            </nav>

            <div id="recept-content">
              <h2>Recept p\xc3\xa5 Pulled Pork</h2>
              <p><strong>Pulled Pork:</strong></p>
              <ul>
                <li>1 kg fl\xc3\xa4skkarr\xc3\xa9</li>
                <li>1 msk malen spiskummin</li>
                <li>33 cl \xc3\xb6l</li>
              </ul>
              <ol>
                <li>Krydda.</li>
                <li>Tillaga.</li>
              </ol>
            </div>
          </body>
        </html>
        """

        data = import_recipe_from_html("https://www.landleyskok.se/recept/pp#recept-content", html)
        self.assertEqual(data.title, "Pulled Pork")
        self.assertIn("1 kg fläskkarré", data.ingredients)
        self.assertNotIn("Receptgeneratorn 2.0", data.ingredients)


