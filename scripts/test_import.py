import os
import sys
import django
import requests

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'receptapp_project.settings')
django.setup()

from recipes.importing import import_recipe_from_url

def test_import():
    url = "https://www.ica.se/recept/pannkakor-grundrecept-5558/"
    print(f"Testing import from: {url}")
    
    try:
        recipe_data = import_recipe_from_url(url)
        print("Import successful!")
        print(f"Title: {recipe_data.title}")
        print(f"Ingredients: {len(recipe_data.ingredients)}")
        print(f"Steps: {len(recipe_data.steps)}")
    except Exception as e:
        print(f"Import failed: {e}")

if __name__ == "__main__":
    test_import()
