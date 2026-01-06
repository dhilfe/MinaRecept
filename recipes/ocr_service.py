import os
import base64
import json
import re
from django.conf import settings
from openai import OpenAI

class ImageRecipeParser:
    def __init__(self):
        # Support both env var names (some deployments use OPEN_API_KEY).
        self.api_key = os.environ.get('OPENAI_API_KEY') or os.environ.get('OPEN_API_KEY')
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
            # Best-effort: preserve original content type if available (png is often better for text).
            content_type = getattr(image_file, "content_type", "") or ""
            if "png" in content_type.lower():
                mime = "image/png"
            else:
                mime = "image/jpeg"

            # Encode image to base64
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """Du är en hjälpsam assistent som extraherar receptinformation från bilder (skärmdumpar/foton).
                        Output ONLY valid JSON with the following structure:
                        {
                            "title": "Recipe Title",
                            "description": "Short description",
                            "ingredients": ["1 cup flour", "2 eggs"],
                            "steps": ["Mix ingredients", "Bake at 200C"],
                            "cooking_time": 30,
                            "servings": 4
                        }
                        Om du ser någon ingredienslista eller instruktioner: returnera dem (även om du är osäker på vissa tecken).
                        Returnera tomma fält ENDAST om bilden inte innehåller recepttext överhuvudtaget.
                        Översätt allt till svenska om det är på ett annat språk.
                        """
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extrahera receptet från bilden. Ingredienser ska vara en rad per ingrediens, och steg ska vara en rad per steg."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                temperature=0,
                max_tokens=1500,
                response_format={ "type": "json_object" }
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)

            # Log basic diagnostics to help with debugging on the Pi.
            try:
                usage = getattr(response, "usage", None)
                if usage is not None:
                    print(f"OCR OpenAI usage: {usage}")
            except Exception:
                pass

            # Guard against models returning ingredients/steps as a single string.
            raw_ingredients = data.get("ingredients", [])
            if isinstance(raw_ingredients, str):
                raw_ingredients = [x.strip() for x in re.split(r"\\r?\\n+", raw_ingredients) if x.strip()]

            raw_steps = data.get("steps", [])
            if isinstance(raw_steps, str):
                raw_steps = [x.strip() for x in re.split(r"\\r?\\n+", raw_steps) if x.strip()]
            
            # Ensure we return the expected format for our views
            return {
                'title': data.get('title', ''),
                'description': data.get('description', ''),
                'ingredients': '\n'.join(raw_ingredients),
                'steps': '\n'.join(raw_steps),
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
