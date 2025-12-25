from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import ShoppingList, ShoppingListItem, Recipe

class ShoppingListLogicTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client = Client()
        self.client.login(username='testuser', password='password')

    def test_main_list_creation(self):
        """Test that a main list is automatically created if none exists when accessing the view."""
        # Ensure no lists exist initially
        ShoppingList.objects.filter(user=self.user).delete()
        
        response = self.client.get(reverse('shopping_lists'))
        self.assertEqual(response.status_code, 200)
        
        # Check that a main list was created
        main_list = ShoppingList.objects.filter(user=self.user, is_main=True).first()
        self.assertIsNotNone(main_list)
        self.assertEqual(main_list.name, "Inköpslista")

    def test_add_to_main_list_by_default(self):
        """Test that ingredients are added to the main list by default if no list_id is provided."""
        # Create a main list
        main_list = ShoppingList.objects.create(user=self.user, name="Main List", is_main=True)
        
        # Create a recipe
        recipe = Recipe.objects.create(
            user=self.user,
            title='Test Recipe',
            ingredients='[{"amount":"1","unit":"st","name":"Gurka"}]',
            steps='Step 1',
            cooking_time=10,
            servings=2
        )
        
        # Post to add ingredients without specifying list_id (simulating API or default behavior)
        # Note: The view 'choose_shopping_list_for_recipe' usually requires list_id in POST, 
        # but let's check the API endpoint or the logic that handles defaults.
        # If we look at api_views.py, the 'add_to_shopping_list' action defaults to main list.
        
        # Let's test the API endpoint for this
        url = reverse('recipe-add-to-shopping-list', args=[recipe.pk])
        response = self.client.post(url) # No data provided
        
        self.assertEqual(response.status_code, 200)
        
        # Verify item is in main list
        item = ShoppingListItem.objects.filter(shopping_list=main_list, name="Gurka").first()
        self.assertIsNotNone(item)
        self.assertEqual(item.amount, "1")

    def test_multiple_lists_separation(self):
        """Test that main list and saved lists are separated."""
        main_list = ShoppingList.objects.create(user=self.user, name="Main", is_main=True)
        saved_list = ShoppingList.objects.create(user=self.user, name="Saved", is_main=False)
        
        response = self.client.get(reverse('shopping_lists'))
        self.assertEqual(response.status_code, 200)
        
        # In the template context or content, we should see both
        self.assertContains(response, "Main")
        self.assertContains(response, "Saved")
        
        # We can't easily check context variables with Client unless we use context_manager or similar,
        # but checking presence in HTML is good enough for now.

    def test_merging_logic_floats(self):
        """Test merging of float values."""
        main_list = ShoppingList.objects.create(user=self.user, name="Main", is_main=True)
        
        # Add 1.5 kg Tomat
        ShoppingListItem.objects.create(user=self.user, shopping_list=main_list, name="Tomat", amount="1.5", unit="kg")
        
        # Add another 0.5 kg Tomat via service/view logic
        # We'll use the service directly to test the logic in isolation
        from .services import upsert_shopping_list_item
        
        upsert_shopping_list_item(self.user, main_list, "Tomat", "0.5", "kg")
        
        item = ShoppingListItem.objects.get(shopping_list=main_list, name="Tomat")
        self.assertEqual(item.amount, "2") # Should be 2 or 2.0 depending on implementation, but likely formatted to remove trailing zero if integer

    def test_merging_logic_strings(self):
        """Test merging of non-numeric values."""
        main_list = ShoppingList.objects.create(user=self.user, name="Main", is_main=True)
        
        # Add "Lite" Salt
        ShoppingListItem.objects.create(user=self.user, shopping_list=main_list, name="Salt", amount="Lite", unit="krm")
        
        # Add "Mer" Salt
        from .services import upsert_shopping_list_item
        upsert_shopping_list_item(self.user, main_list, "Salt", "Mer", "krm")
        
        item = ShoppingListItem.objects.get(shopping_list=main_list, name="Salt")
        # Expecting concatenation: "Lite + Mer"
        self.assertEqual(item.amount, "Lite + Mer")
