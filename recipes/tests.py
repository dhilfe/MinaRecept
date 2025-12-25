from django.test import TestCase, Client
from django.contrib.messages import get_messages
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Recipe, WeeklyPlan, WeeklyMenu, ShoppingList, ShoppingListItem
from unittest.mock import patch, MagicMock
import requests
from datetime import date, timedelta
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from pathlib import Path

class RecipeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client = Client()
        self.client.login(username='testuser', password='password')

        self.shopping_list = ShoppingList.objects.create(user=self.user, name='Inköpslista', is_recurring=False)
        
        self.recipe = Recipe.objects.create(
            user=self.user,
            title='Test Recipe',
            description='Test Description',
            ingredients='[{"amount":"1","unit":"st","name":"Tomat"},{"amount":"2","unit":"dl","name":"Ris"}]',
            steps='Step 1\nStep 2',
            cooking_time=30,
            difficulty='easy',
            dish_type='everyday',
            servings=4
        )

    def test_recipe_list_view(self):
        response = self.client.get(reverse('recipe_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Recipe')
        self.assertContains(response, reverse('recipe_cook', args=[self.recipe.pk]) + '?reset=1')

    def test_recipe_detail_view(self):
        response = self.client.get(reverse('recipe_detail', args=[self.recipe.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Recipe')
        self.assertContains(response, 'Tomat')
        self.assertContains(response, reverse('recipe_cook', args=[self.recipe.pk]) + '?reset=1')

    def test_recipe_cook_view_requires_login(self):
        anon = Client()
        response = anon.get(reverse('recipe_cook', args=[self.recipe.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_recipe_cook_view(self):
        response = self.client.get(reverse('recipe_cook', args=[self.recipe.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Recipe')

    def test_recipe_detail_has_add_to_shopping_list_button(self):
        """Ensure the 'Add to shopping list' button is present on the recipe detail page."""
        response = self.client.get(reverse('recipe_detail', args=[self.recipe.pk]))
        self.assertEqual(response.status_code, 200)
        # Check for the link to choose_shopping_list_for_recipe
        expected_url = reverse('choose_shopping_list_for_recipe', args=[self.recipe.pk])
        self.assertContains(response, expected_url)
        self.assertContains(response, 'Lägg till i inköpslista')

    def test_add_ingredients_to_shopping_list(self):
        response = self.client.post(
            reverse('choose_shopping_list_for_recipe', args=[self.recipe.pk]),
            {'list_id': str(self.shopping_list.id)},
        )
        self.assertEqual(response.status_code, 302)
        tomat = ShoppingListItem.objects.get(user=self.user, shopping_list=self.shopping_list, name__iexact='Tomat')
        ris = ShoppingListItem.objects.get(user=self.user, shopping_list=self.shopping_list, name__iexact='Ris')
        self.assertEqual(tomat.unit, 'st')
        self.assertEqual(tomat.amount, '1')
        self.assertEqual(ris.unit, 'dl')
        self.assertEqual(ris.amount, '2')

        # Adding again from same recipe should be blocked (no duplicates)
        before = ShoppingListItem.objects.filter(user=self.user, shopping_list=self.shopping_list).count()
        response2 = self.client.post(
            reverse('choose_shopping_list_for_recipe', args=[self.recipe.pk]),
            {'list_id': str(self.shopping_list.id)},
        )
        self.assertEqual(response2.status_code, 302)
        after = ShoppingListItem.objects.filter(user=self.user, shopping_list=self.shopping_list).count()
        self.assertEqual(before, after)

    def test_shopping_list_edit(self):
        item = ShoppingListItem.objects.create(user=self.user, shopping_list=self.shopping_list, name='Mjölk', amount='1', unit='l')
        response = self.client.post(reverse('shopping_list_detail', args=[self.shopping_list.id]), {
            'action': 'save',
            f'name_{item.id}': 'Mjölk',
            f'amount_{item.id}': '2',
            f'unit_{item.id}': 'l',
            f'checked_{item.id}': 'on',
        })
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.amount, '2')
        self.assertTrue(item.checked)

    def test_shopping_list_merge_integer_and_missing_amount(self):
        # Existing item with amount 2
        ShoppingListItem.objects.create(
            user=self.user,
            shopping_list=self.shopping_list,
            name='Tomat',
            amount='2',
            unit='st',
            checked=False,
        )

        # Add from recipe: 1 Tomat should merge -> 3 (not 3,0)
        self.client.post(
            reverse('choose_shopping_list_for_recipe', args=[self.recipe.pk]),
            {'list_id': str(self.shopping_list.id)},
        )
        tomat = ShoppingListItem.objects.get(user=self.user, shopping_list=self.shopping_list, name__iexact='Tomat')
        self.assertEqual(tomat.amount, '3')

        # Add manually without amount should count as +1
        self.client.post(
            reverse('shopping_list_detail', args=[self.shopping_list.id]),
            {'add_new': '1', 'new_name': 'Tomat', 'new_amount': '', 'new_unit': 'st'},
        )
        tomat.refresh_from_db()
        self.assertEqual(tomat.amount, '4')

    def test_shopping_list_import_skips_header_lines(self):
        recipe = Recipe.objects.create(
            user=self.user,
            title='Header Recipe',
            ingredients='Fyllning:\n2 dl mjöl\nSås:\n1 st tomat',
            steps='x',
            cooking_time=10,
            servings=2,
        )

        self.client.post(
            reverse('choose_shopping_list_for_recipe', args=[recipe.pk]),
            {'list_id': str(self.shopping_list.id)},
        )

        names = set(
            ShoppingListItem.objects.filter(user=self.user, shopping_list=self.shopping_list)
            .values_list('name', flat=True)
        )
        self.assertIn('mjöl', {n.lower() for n in names})
        self.assertIn('tomat', {n.lower() for n in names})
        self.assertNotIn('fyllning:', {n.lower() for n in names})
        self.assertNotIn('sås:', {n.lower() for n in names})

    def test_create_recipe(self):
        response = self.client.post(reverse('recipe_create'), {
            'title': 'New Recipe',
            'ingredients': '[{"amount":"1","unit":"st","name":"Tomat"}]',
            'steps': 'New Step',
            'cooking_time': 15,
            'difficulty': 'medium',
            'dish_type': 'party',
            'servings': 2
        })
        self.assertEqual(response.status_code, 302) # Redirects to list
        self.assertTrue(Recipe.objects.filter(title='New Recipe').exists())

    def test_weekly_plan(self):
        # Add to weekly plan
        WeeklyPlan.objects.create(user=self.user, day='mon', recipe=self.recipe)
        
        response = self.client.get(reverse('weekly_plan'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Recipe')
        
    def test_random_menu(self):
        # Create enough recipes
        for i in range(6):
            Recipe.objects.create(
                user=self.user,
                title=f'Recipe {i}',
                cooking_time=10,
                servings=2
            )
            
        response = self.client.post(reverse('generate_random_menu'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(WeeklyPlan.objects.filter(user=self.user).count(), 7)

    def test_random_menu_with_filters(self):
        # Create recipes with different types
        Recipe.objects.create(user=self.user, title='Veg', dish_type='vegetarian', cooking_time=20)
        Recipe.objects.create(user=self.user, title='Meat', dish_type='everyday', cooking_time=40)
        
        # Filter for vegetarian
        response = self.client.post(reverse('generate_random_menu'), {
            'include_types': ['vegetarian']
        })
        self.assertEqual(response.status_code, 302)
        # Should only pick the vegetarian one (repeatedly)
        plans = WeeklyPlan.objects.filter(user=self.user)
        self.assertEqual(plans.count(), 7)
        for plan in plans:
            self.assertEqual(plan.recipe.title, 'Veg')

    def test_save_weekly_menu_custom_name(self):
        WeeklyPlan.objects.create(user=self.user, day='mon', recipe=self.recipe)
        response = self.client.post(reverse('save_weekly_menu'), {'menu_name': 'Julvecka'})
        self.assertEqual(response.status_code, 302)
        menu = WeeklyMenu.objects.get(user=self.user)
        self.assertEqual(menu.name, 'Julvecka')
        self.assertEqual(menu.items.count(), 1)

    def test_save_weekly_menu_default_next_week_number(self):
        WeeklyPlan.objects.create(user=self.user, day='mon', recipe=self.recipe)
        response = self.client.post(reverse('save_weekly_menu'), {'menu_name': ''})
        self.assertEqual(response.status_code, 302)
        menu = WeeklyMenu.objects.get(user=self.user)

        iso = (date.today() + timedelta(days=7)).isocalendar()
        expected_week = int(iso.week)
        expected_year = int(iso.year)

        self.assertEqual(menu.name, f"Vecka {expected_week}")
        self.assertEqual(menu.week_number, expected_week)
        self.assertEqual(menu.year, expected_year)

    @patch('recipes.views.requests.get')
    def test_import_recipe(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Test with JSON-LD
        json_ld = """
        <script type="application/ld+json">
        {
            "@context": "https://schema.org/",
            "@type": "Recipe",
            "name": "JSON Recipe",
            "description": "A good recipe",
            "image": ["https://example.com/img.jpg"],
            "recipeIngredient": ["1 cup flour", "2 eggs"],
            "recipeInstructions": [{"@type": "HowToStep", "text": "Mix it."}],
            "totalTime": "PT1H"
        }
        </script>
        """
        mock_response.content = json_ld.encode('utf-8')
        mock_get.return_value = mock_response

        response = self.client.post(reverse('recipe_import'), {
            'url': 'example.com/recipe' # Test without http
        })
        self.assertEqual(response.status_code, 302)
        data = self.client.session['import_data']
        self.assertEqual(data['title'], 'JSON Recipe')
        self.assertIn('1 cup flour', data['ingredients'])
        self.assertIn('Mix it.', data['steps'])
        self.assertEqual(data['cooking_time'], 60)
        self.assertEqual(data.get('imported_image_url'), 'https://example.com/img.jpg')

    @patch('recipes.views.requests.get')
    def test_import_recipe_retry_www(self, mock_get):
        # First call fails, second succeeds
        mock_response_fail = MagicMock()
        mock_response_fail.raise_for_status.side_effect = requests.RequestException("Fail")
        
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.content = b'<html><title>WWW Recipe</title></html>'
        
        mock_get.side_effect = [requests.RequestException("Fail"), mock_response_success]

        response = self.client.post(reverse('recipe_import'), {
            'url': 'example.com'
        })
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(mock_get.call_count, 2)
        # Check that second call had www
        args, _ = mock_get.call_args_list[1]
        self.assertEqual(args[0], 'https://www.example.com')

    @patch('recipes.views.instaloader.Instaloader')
    @patch('recipes.views.instaloader.Post')
    def test_import_recipe_instagram_instaloader(self, mock_post, mock_instaloader):
        # Mock Instaloader behavior
        mock_loader_instance = MagicMock()
        mock_instaloader.return_value = mock_loader_instance
        
        mock_post_instance = MagicMock()
        mock_post_instance.owner_username = 'testuser'
        mock_post_instance.caption = 'My Insta Recipe\n\nIngredients:\n- 1 egg\n\nSteps:\n1. Cook it.'
        mock_post_instance.url = 'http://insta.com/image.jpg'
        
        mock_post.from_shortcode.return_value = mock_post_instance

        response = self.client.post(reverse('recipe_import'), {
            'url': 'https://instagram.com/p/123'
        })
        
        self.assertEqual(response.status_code, 302)
        data = self.client.session['import_data']
        
        # Should use simplified import (Title + Full Text in Helper)
        self.assertEqual(data['title'], 'My Insta Recipe')
        self.assertEqual(data['ingredients'], '') # Should be empty now
        self.assertEqual(data['steps'], '')       # Should be empty now
        
        # Description should be clean
        self.assertIn('(Importerad från Instagram: https://instagram.com/p/123)', data['description'])
        
        # Raw text should be in imported_text
        self.assertIn('My Insta Recipe\n\nIngredients:\n- 1 egg\n\nSteps:\n1. Cook it.', data['imported_text'])
        self.assertEqual(data['imported_image_url'], 'http://insta.com/image.jpg')

    @patch('recipes.views.requests.get')
    def test_import_recipe_fallback_og(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Test with OG tags but no JSON-LD
        html = """
        <html>
        <head>
            <title>Instagram</title>
            <meta property="og:title" content="User on Instagram: &quot;My Recipe Title&quot;" />
            <meta property="og:description" content="Here is the recipe description." />
            <meta property="og:image" content="http://example.com/image.jpg" />
        </head>
        <body>
            <p>Some random text</p>
        </body>
        </html>
        """
        mock_response.content = html.encode('utf-8')
        mock_get.return_value = mock_response

        response = self.client.post(reverse('recipe_import'), {
            'url': 'https://instagram.com/p/123'
        })
        self.assertEqual(response.status_code, 302)
        data = self.client.session['import_data']
        # Title should be cleaned
        self.assertEqual(data['title'], 'My Recipe Title')
        # Description should come from og:description
        self.assertIn('Here is the recipe description.', data['description'])
        # Image URL should be passed through for optional download/save
        self.assertEqual(data.get('imported_image_url'), 'http://example.com/image.jpg')

    @patch('recipes.views.requests.get')
    def test_import_recipe_timeout_shows_user_friendly_error(self, mock_get):
        mock_get.side_effect = requests.Timeout("timeout")

        response = self.client.post(reverse('recipe_import'), {
            'url': 'https://example.com/recipe'
        })

        self.assertEqual(response.status_code, 200)
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('Tidsgränsen' in m for m in msgs))

    @patch('recipes.views.requests.get')
    def test_import_recipe_http_error_shows_status_code(self, mock_get):
        mock_response = MagicMock()
        http_err = requests.HTTPError("404")
        http_err.response = MagicMock(status_code=404)
        mock_response.raise_for_status.side_effect = http_err
        mock_get.return_value = mock_response

        response = self.client.post(reverse('recipe_import'), {
            'url': 'https://example.com/recipe'
        })

        self.assertEqual(response.status_code, 200)
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('HTTP 404' in m for m in msgs))

    def _load_import_fixture(self, filename: str) -> bytes:
        base = Path(__file__).resolve().parent / 'test_fixtures' / 'import'
        return (base / filename).read_bytes()

    @patch('recipes.views.requests.get')
    def test_import_recipe_fixture_landleyskok(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = self._load_import_fixture('landleyskok.se.html')
        mock_get.return_value = mock_response

        response = self.client.post(reverse('recipe_import'), {'url': 'https://landleyskok.se/recept/test'})
        self.assertEqual(response.status_code, 302)
        data = self.client.session['import_data']
        self.assertEqual(data['title'], 'Landleyskok Fixture Recipe')
        self.assertIn('1 dl mjöl', data['ingredients'])
        self.assertIn('Blanda torra ingredienser.', data['steps'])
        self.assertIn('Vispa ner ägg.', data['steps'])

    @patch('recipes.views.requests.get')
    def test_import_recipe_fixture_ica(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = self._load_import_fixture('ica.se.html')
        mock_get.return_value = mock_response

        response = self.client.post(reverse('recipe_import'), {'url': 'https://ica.se/recept/test'})
        self.assertEqual(response.status_code, 302)
        data = self.client.session['import_data']
        self.assertEqual(data['title'], 'ICA Fixture Recipe')
        self.assertIn('3 msk olja', data['ingredients'])
        self.assertIn('Värm oljan.', data['steps'])

    @patch('recipes.views.requests.get')
    def test_import_recipe_fixture_coop(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = self._load_import_fixture('coop.se.html')
        mock_get.return_value = mock_response

        response = self.client.post(reverse('recipe_import'), {'url': 'https://coop.se/recept/test'})
        self.assertEqual(response.status_code, 302)
        data = self.client.session['import_data']
        self.assertEqual(data['title'], 'Coop Fixture Recipe')
        self.assertIn('1 st lök', data['ingredients'])
        self.assertIn('Hacka lök.', data['steps'])
        self.assertIn('Fräs i panna.', data['steps'])
        self.assertIn('Servera.', data['steps'])

    @patch('recipes.views.requests.get')
    def test_import_recipe_fixture_koket(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = self._load_import_fixture('koket.se.html')
        mock_get.return_value = mock_response

        response = self.client.post(reverse('recipe_import'), {'url': 'https://koket.se/recept/test'})
        self.assertEqual(response.status_code, 302)
        data = self.client.session['import_data']
        self.assertEqual(data['title'], 'Köket Fixture Recipe')
        self.assertIn('200 g pasta', data['ingredients'])
        self.assertIn('Koka pastan.', data['steps'])
        self.assertIn('Häll av och blanda.', data['steps'])


class ApiTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='apiuser1', password='password1')
        self.user2 = User.objects.create_user(username='apiuser2', password='password2')

        self.recipe1 = Recipe.objects.create(
            user=self.user1,
            title='User1 Recipe',
            ingredients='[]',
            steps='x',
            cooking_time=10,
            servings=2,
        )
        self.recipe2 = Recipe.objects.create(
            user=self.user2,
            title='User2 Recipe',
            ingredients='[]',
            steps='y',
            cooking_time=12,
            servings=3,
        )

        self.client_api = APIClient()

        self.token1 = Token.objects.create(user=self.user1)

    def _auth1(self):
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Token {self.token1.key}')

    @patch('recipes.importing.requests.get')
    def test_import_recipe_api_creates_recipe_from_fixture(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        fixture_path = Path(__file__).resolve().parent / 'test_fixtures' / 'import' / 'ica.se.html'
        mock_response.content = fixture_path.read_bytes()
        mock_get.return_value = mock_response

        self._auth1()
        response = self.client_api.post('/api/recipes/import/', {'url': 'https://ica.se/recept/test'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['title'], 'ICA Fixture Recipe')

        # Ensure it belongs to user1
        recipe_id = response.data['id']
        created = Recipe.objects.get(id=recipe_id)
        self.assertEqual(created.user_id, self.user1.id)
        self.assertIn('Värm oljan.', created.steps)

    def test_api_token_obtain(self):
        response = self.client_api.post(
            '/api/auth/token/',
            {'username': 'apiuser1', 'password': 'password1'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)

    def test_api_requires_auth(self):
        response = self.client_api.get('/api/recipes/')
        self.assertIn(response.status_code, [401, 403])

        token, _ = Token.objects.get_or_create(user=self.user1)
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        authed = self.client_api.get('/api/recipes/')
        self.assertEqual(authed.status_code, 200)

    def test_api_recipes_scoped_to_user(self):
        token, _ = Token.objects.get_or_create(user=self.user1)
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client_api.get('/api/recipes/')
        self.assertEqual(response.status_code, 200)
        titles = [r['title'] for r in response.data]
        self.assertIn('User1 Recipe', titles)
        self.assertNotIn('User2 Recipe', titles)

    def test_cannot_create_weekly_plan_with_other_users_recipe(self):
        token, _ = Token.objects.get_or_create(user=self.user1)
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client_api.post(
            '/api/weekly-plan/',
            {'day': 'mon', 'recipe': self.recipe2.id},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_cannot_create_shopping_item_on_other_users_list(self):
        other_list = ShoppingList.objects.create(user=self.user2, name='Other list')

        token, _ = Token.objects.get_or_create(user=self.user1)
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client_api.post(
            '/api/shopping-list-items/',
            {
                'shopping_list': other_list.id,
                'name': 'Tomat',
                'amount': '1',
                'unit': 'st',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
