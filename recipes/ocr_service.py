import os
import base64
import json
from django.conf import settings
from openai import OpenAI

class ImageRecipeParser:
    def __init__(self):
        self.api_key = os.environ.get('OPENAI_API_KEY')
        self.client = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)

    def parse_image(self, image_file):
        """
        Parses a recipe image and returns a dict with title, ingredients, steps.
        """
        if not self.api_key:
            return self._mock_parse()

        try:
            # Encode image to base64
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a helpful assistant that extracts recipe information from images. 
                        Output ONLY valid JSON with the following structure:
                        {
                            "title": "Recipe Title",
                            "description": "Short description",
                            "ingredients": ["1 cup flour", "2 eggs"],
                            "steps": ["Mix ingredients", "Bake at 200C"],
                            "cooking_time": 30,
                            "servings": 4
                        }
                        If you cannot find a recipe, return empty strings/lists.
                        Translate everything to Swedish if it's in another language.
                        """
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract the recipe from this image."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                response_format={ "type": "json_object" }
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)
            
            # Ensure we return the expected format for our views
            return {
                'title': data.get('title', ''),
                'description': data.get('description', ''),
                'ingredients': '\n'.join(data.get('ingredients', [])),
                'steps': '\n'.join(data.get('steps', [])),
                'cooking_time': data.get('cooking_time', 0),
                'servings': data.get('servings', 4),
            }
            
        except Exception as e:
            print(f"OpenAI Error: {e}")
            # Fallback to mock or error
            return {
                'title': 'Kunde inte tolka bild',
                'description': f'Ett fel uppstod vid analysen: {str(e)}',
                'ingredients': '',
                'steps': '',
            }

    def _mock_parse(self):
        """Mock response for testing without API key."""
        return {
            'title': 'Mockat Recept från Bild',
            'description': 'Detta är ett testrecept eftersom ingen API-nyckel hittades. (Mock)',
            'ingredients': '2 st Ägg\n3 dl Mjöl\n5 dl Mjölk\n1 tsk Salt\nSmör till stekning',
            'steps': '1. Vispa ihop ägg och hälften av mjölken.\n2. Tillsätt mjöl och vispa till en slät smet.\n3. Tillsätt resten av mjölken och salt.\n4. Stek tunna pannkakor i smör.',
            'cooking_time': 20,
            'servings': 4
        }
