from django.test import TestCase
from django.urls import reverse

class PrivacyTermsPublicTests(TestCase):
    def test_privacy_policy_public(self):
        response = self.client.get(reverse('privacy_policy'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Integritetspolicy', response.content.decode())

    def test_terms_public(self):
        response = self.client.get(reverse('terms'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Användarvillkor', response.content.decode())
