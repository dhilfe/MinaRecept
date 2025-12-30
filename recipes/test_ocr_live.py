import os
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from io import BytesIO
from unittest import skipUnless
from recipes.ocr_service import ImageRecipeParser

class OCRIntegrationLiveAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ocruser2', password='password')
        self.client = Client()
        self.client.login(username='ocruser2', password='password')

    @skipUnless(os.environ.get('OPENAI_API_KEY'), "Requires OPENAI_API_KEY env var set for live OCR test.")
    def test_ocr_service_with_real_openai(self):
        parser = ImageRecipeParser()
        # Use a real small test image (should be a valid recipe image in binary form)
        # For demonstration, we use a blank JPEG header (will return empty/failed result)
        image = BytesIO(b"\xff\xd8\xff\xe0" + b"0"*1000)  # Minimal JPEG
        image.name = 'test.jpg'
        data = parser.parse_image(image)
        # Should return a dict with expected keys
        self.assertIn('title', data)
        self.assertIn('ingredients', data)
        self.assertIn('steps', data)
        # Should not crash, even if OCR result is empty

    @skipUnless(os.environ.get('OPENAI_API_KEY'), "Requires OPENAI_API_KEY env var set for live OCR test.")
    @override_settings(DEBUG=True)
    def test_recipe_import_image_view_with_real_openai(self):
        # Use a real small test image (should be a valid recipe image in binary form)
        image = BytesIO(b"\xff\xd8\xff\xe0" + b"0"*1000)
        image.name = 'test.jpg'
        response = self.client.post(reverse('recipe_import_image'), {'recipe_image': image})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('recipe_create'), response['Location'])
        session_data = self.client.session['import_data']
        self.assertIn('title', session_data)
        self.assertIn('ingredients', session_data)
        self.assertIn('steps', session_data)
