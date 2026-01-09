from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from recipes.models import Recipe


class CookbookApiTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.client = APIClient()
        self.user = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="pass12345",
        )
        self.other_user = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="pass12345",
        )

        self.client.force_authenticate(user=self.user)

    def test_cookbooks_list_empty(self):
        resp = self.client.get("/api/cookbooks/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])

    def test_cookbooks_create_and_list(self):
        create_resp = self.client.post("/api/cookbooks/", {"name": "Mina favoriter"}, format="json")
        self.assertEqual(create_resp.status_code, 201)
        self.assertEqual(create_resp.data["name"], "Mina favoriter")

        list_resp = self.client.get("/api/cookbooks/")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.data), 1)
        self.assertEqual(list_resp.data[0]["name"], "Mina favoriter")
        self.assertEqual(list_resp.data[0]["recipe_count"], 0)

    def test_cookbooks_unique_per_user(self):
        resp1 = self.client.post("/api/cookbooks/", {"name": "Min kokbok"}, format="json")
        self.assertEqual(resp1.status_code, 201)

        resp2 = self.client.post("/api/cookbooks/", {"name": "Min kokbok"}, format="json")
        self.assertEqual(resp2.status_code, 400)

        other_client = APIClient()
        other_client.force_authenticate(user=self.other_user)
        resp3 = other_client.post("/api/cookbooks/", {"name": "Min kokbok"}, format="json")
        self.assertEqual(resp3.status_code, 201)

    def test_add_recipe_requires_ownership(self):
        cookbook_resp = self.client.post("/api/cookbooks/", {"name": "Test"}, format="json")
        self.assertEqual(cookbook_resp.status_code, 201)
        cookbook_id = cookbook_resp.data["id"]

        other_recipe = Recipe.objects.create(
            user=self.other_user,
            title="Other user's recipe",
            ingredients="1 thing",
            steps="do it",
            cooking_time=10,
        )

        add_resp = self.client.post(
            f"/api/cookbooks/{cookbook_id}/add-recipe/",
            {"recipe_id": other_recipe.id},
            format="json",
        )
        self.assertEqual(add_resp.status_code, 404)

    def test_add_recipe_success_and_idempotent(self):
        cookbook_resp = self.client.post("/api/cookbooks/", {"name": "Test"}, format="json")
        self.assertEqual(cookbook_resp.status_code, 201)
        cookbook_id = cookbook_resp.data["id"]

        recipe = Recipe.objects.create(
            user=self.user,
            title="My recipe",
            ingredients="1 thing",
            steps="do it",
            cooking_time=10,
        )

        add1 = self.client.post(
            f"/api/cookbooks/{cookbook_id}/add-recipe/",
            {"recipe_id": recipe.id},
            format="json",
        )
        self.assertEqual(add1.status_code, 200)

        add2 = self.client.post(
            f"/api/cookbooks/{cookbook_id}/add-recipe/",
            {"recipe_id": recipe.id},
            format="json",
        )
        self.assertEqual(add2.status_code, 200)

        list_resp = self.client.get("/api/cookbooks/")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.data[0]["recipe_count"], 1)

    def test_list_cookbook_recipes(self):
        cookbook_resp = self.client.post("/api/cookbooks/", {"name": "Middag"}, format="json")
        self.assertEqual(cookbook_resp.status_code, 201)
        cookbook_id = cookbook_resp.data["id"]

        recipe1 = Recipe.objects.create(
            user=self.user,
            title="Pasta",
            ingredients="1 thing",
            steps="do it",
            cooking_time=10,
        )
        recipe2 = Recipe.objects.create(
            user=self.user,
            title="Soppa",
            ingredients="1 thing",
            steps="do it",
            cooking_time=10,
        )

        add_resp = self.client.post(
            f"/api/cookbooks/{cookbook_id}/add-recipe/",
            {"recipe_id": recipe2.id},
            format="json",
        )
        self.assertEqual(add_resp.status_code, 200)

        list_resp = self.client.get(f"/api/cookbooks/{cookbook_id}/recipes/")
        self.assertEqual(list_resp.status_code, 200)
        titles = {r["title"] for r in list_resp.data}
        self.assertIn("Soppa", titles)
        self.assertNotIn("Pasta", titles)
