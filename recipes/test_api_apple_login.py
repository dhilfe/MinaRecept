from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth.models import User

from rest_framework.test import APIClient


class AppleLoginAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_missing_id_token_returns_400(self):
        resp = self.client.post("/api/auth/apple/", data={}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("detail", resp.json())

    @patch("recipes.api_views.jwt.decode")
    @patch("recipes.api_views.jwt.get_unverified_header")
    @patch("recipes.api_views.AppleLoginView.get_apple_keys")
    def test_first_login_creates_user_and_returns_token(
        self, mock_get_keys, mock_get_header, mock_decode
    ):
        mock_get_keys.return_value = [{"kid": "kid1"}]
        mock_get_header.return_value = {"kid": "kid1"}
        mock_decode.return_value = {"sub": "apple-sub-123", "email": "user@example.com"}

        resp = self.client.post(
            "/api/auth/apple/",
            data={
                "id_token": "dummy",
                "first_name": "Test",
                "last_name": "User",
            },
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("token", data)
        self.assertEqual(data["email"], "user@example.com")

        user = User.objects.get(username="apple-sub-123")
        self.assertEqual(user.email, "user@example.com")
        self.assertEqual(user.first_name, "Test")
        self.assertEqual(user.last_name, "User")

    @patch("recipes.api_views.jwt.decode")
    @patch("recipes.api_views.jwt.get_unverified_header")
    @patch("recipes.api_views.AppleLoginView.get_apple_keys")
    def test_sub_match_reuses_existing_user(self, mock_get_keys, mock_get_header, mock_decode):
        existing = User.objects.create_user(
            username="apple-sub-123", email="user@example.com", password=None
        )

        mock_get_keys.return_value = [{"kid": "kid1"}]
        mock_get_header.return_value = {"kid": "kid1"}
        mock_decode.return_value = {"sub": "apple-sub-123", "email": "user@example.com"}

        resp = self.client.post("/api/auth/apple/", data={"id_token": "dummy"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.filter(username="apple-sub-123").count(), 1)
        self.assertEqual(User.objects.get(username="apple-sub-123").id, existing.id)

    @patch("recipes.api_views.jwt.decode")
    @patch("recipes.api_views.jwt.get_unverified_header")
    @patch("recipes.api_views.AppleLoginView.get_apple_keys")
    def test_missing_sub_claim_returns_400(self, mock_get_keys, mock_get_header, mock_decode):
        mock_get_keys.return_value = [{"kid": "kid1"}]
        mock_get_header.return_value = {"kid": "kid1"}
        mock_decode.return_value = {"email": "user@example.com"}

        resp = self.client.post("/api/auth/apple/", data={"id_token": "dummy"}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("detail", resp.json())


