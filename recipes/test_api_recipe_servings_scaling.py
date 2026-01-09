from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from recipes.models import Recipe


class RecipeServingsScalingApiTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.client = APIClient()
        self.user = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="pass12345",
        )
        self.client.force_authenticate(user=self.user)

    def test_create_recipe_normalizes_ingredients_to_json(self):
        payload = {
            "title": "Test",
            "description": "",
            "ingredients": "2 dl mjöl\n1/2 tsk salt",
            "steps": "Blanda",
            "cooking_time": 10,
            "dish_type": "lunch_dinner",
            "tags": "",
            "servings": 4,
        }

        resp = self.client.post("/api/recipes/", payload, format="json")
        self.assertEqual(resp.status_code, 201)

        # iOS expects a JSON string that decodes to a list of objects.
        self.assertIsInstance(resp.data["ingredients"], str)
        self.assertTrue(resp.data["ingredients"].strip().startswith("["))

    def test_patch_servings_scales_existing_ingredients_amounts(self):
        recipe = Recipe.objects.create(
            user=self.user,
            title="My recipe",
            ingredients='[{"amount":"2","unit":"dl","name":"Ris"}]',
            steps="Do it",
            cooking_time=10,
            servings=4,
        )

        resp = self.client.patch(
            f"/api/recipes/{recipe.id}/",
            {"servings": 8},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["servings"], 8)
        self.assertIn('"amount":"4"', resp.data["ingredients"])

    def test_patch_servings_does_not_rescale_if_client_sends_ingredients(self):
        recipe = Recipe.objects.create(
            user=self.user,
            title="My recipe",
            ingredients='[{"amount":"2","unit":"dl","name":"Ris"}]',
            steps="Do it",
            cooking_time=10,
            servings=4,
        )

        resp = self.client.patch(
            f"/api/recipes/{recipe.id}/",
            {"servings": 8, "ingredients": '[{"amount":"999","unit":"dl","name":"Ris"}]'},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["servings"], 8)
        self.assertIn('"amount":"999"', resp.data["ingredients"])
