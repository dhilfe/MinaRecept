from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import mail

class EmailVerificationAndPasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='verify@test.com', email='verify@test.com', password='TestPassword123!')

    def test_password_reset_sends_email(self):
        response = self.client.post(reverse('password_reset'), {'email': 'verify@test.com'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('verify@test.com', mail.outbox[0].to)

    def test_signup_creates_user_and_redirects(self):
        """
        This project uses a minimal custom signup view (email + password) that logs the user in directly.
        Apple Sign-In is handled via a separate API endpoint.
        """
        response = self.client.post(
            reverse("signup"),
            {
                "email": "newverify@test.com",
                "password1": "TestPassword123!",
                "password2": "TestPassword123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="newverify@test.com").exists())
