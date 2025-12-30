from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings
from unittest.mock import patch

class RateLimitSecurityTests(TestCase):
    def test_signup_rate_limit(self):
        if not getattr(settings, "RATELIMIT_ENABLE", True):
            self.skipTest("Rate limiting is disabled during test runs to avoid cross-test flakiness.")
        for i in range(5):
            response = self.client.post(reverse('signup'), {
                'email': f'user{i}@test.com',
                'password1': 'TestPassword123!',
                'password2': 'TestPassword123!',
            })
        # 6th request should be blocked
        response = self.client.post(reverse('signup'), {
            'email': 'user6@test.com',
            'password1': 'TestPassword123!',
            'password2': 'TestPassword123!',
        })
        self.assertIn(response.status_code, (429, 403))

    def test_login_rate_limit(self):
        if not getattr(settings, "RATELIMIT_ENABLE", True):
            self.skipTest("Rate limiting is disabled during test runs to avoid cross-test flakiness.")
        User.objects.create_user(username='testuser', email='testuser@test.com', password='TestPassword123!')
        for i in range(10):
            self.client.post(reverse('login'), {
                'username': 'testuser@test.com',
                'password': 'wrongpassword',
            })
        # 11th request should be blocked
        response = self.client.post(reverse('login'), {
            'username': 'testuser@test.com',
            'password': 'wrongpassword',
        })
        self.assertIn(response.status_code, (429, 403))

    def test_signup_email_validation(self):
        User.objects.create_user(username='exists@test.com', email='exists@test.com', password='TestPassword123!')
        response = self.client.post(reverse('signup'), {
            'email': 'exists@test.com',
            'password1': 'TestPassword123!',
            'password2': 'TestPassword123!',
        })
        self.assertContains(response, 'E-postadressen används redan.', status_code=200)
