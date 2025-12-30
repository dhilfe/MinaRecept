from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from io import BytesIO
from unittest.mock import patch
from recipes.ocr_service import ImageRecipeParser

class OCRImportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ocruser', password='password')
        self.client = Client()
        self.client.login(username='ocruser', password='password')

    @patch('recipes.ocr_service.ImageRecipeParser.parse_image')
    def test_recipe_import_image_view(self, mock_parse_image):
        # Arrange: mock OCR result
        mock_parse_image.return_value = {
            'title': 'OCR Pannkakor',
            'description': 'Testrecept från bild',
            'ingredients': '2 st Ägg\n3 dl Mjöl',
            'steps': '1. Vispa ihop\n2. Stek',
            'cooking_time': 15,
            'servings': 4
        }
        # Simulate image upload
        image = BytesIO(b"fake image data")
        image.name = 'test.jpg'
        response = self.client.post(reverse('recipe_import_image'), {'recipe_image': image})
        # Should redirect to recipe_create
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('recipe_create'), response['Location'])
        # Data should be in session
        session_data = self.client.session['import_data']
        self.assertEqual(session_data['title'], 'OCR Pannkakor')
        self.assertIn('Ägg', session_data['ingredients'])

    def test_ocr_service_mock_parse(self):
        parser = ImageRecipeParser()
        data = parser._mock_parse()
        self.assertIn('Mockat Recept', data['title'])
        self.assertIn('Ägg', data['ingredients'])
