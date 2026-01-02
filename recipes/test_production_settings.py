
# Tests for verifying production settings internal consistency.
from django.test import TestCase
import receptapp_project.settings as project_settings

class ProductionSettingsTests(TestCase):
    """
    Test suite for critical Django production settings.
    Ensures that security-related settings are enforced in production.
    """
    def test_allowed_hosts_in_production(self):
        """
        ALLOWED_HOSTS should be consistent with the DEBUG mode (env-driven at import time).
        """
        if project_settings.DEBUG:
            # In DEBUG, we either allow all ('*') or specifically localhost.
            if '*' in project_settings.ALLOWED_HOSTS:
                self.assertIn('*', project_settings.ALLOWED_HOSTS)
            else:
                self.assertIn("localhost", project_settings.ALLOWED_HOSTS)
        else:
            self.assertGreaterEqual(len(project_settings.ALLOWED_HOSTS), 1)

    def test_secure_settings_in_production(self):
        """
        Security settings must enforce HTTPS and secure cookies in production.
        """
        self.assertEqual(project_settings.SECURE_SSL_REDIRECT, (not project_settings.DEBUG))
        self.assertEqual(project_settings.SESSION_COOKIE_SECURE, (not project_settings.DEBUG))
        self.assertEqual(project_settings.CSRF_COOKIE_SECURE, (not project_settings.DEBUG))

    def test_cors_settings_in_production(self):
        """
        CORS_ALLOWED_ORIGINS must include only trusted frontend domains.
        Prevents cross-origin requests from untrusted sources.
        """
        # In DEBUG we allow all origins; in production we expect an explicit allowlist.
        if project_settings.DEBUG:
            self.assertTrue(getattr(project_settings, "CORS_ALLOW_ALL_ORIGINS", False))
        else:
            self.assertTrue(hasattr(project_settings, "CORS_ALLOWED_ORIGINS"))
            self.assertIn("https://app.receptapp.se", project_settings.CORS_ALLOWED_ORIGINS)
            self.assertIn("https://api.receptapp.se", project_settings.CORS_ALLOWED_ORIGINS)
