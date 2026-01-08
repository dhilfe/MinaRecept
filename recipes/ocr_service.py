import os
import base64
import json
import re
import logging
from io import BytesIO
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

class ImageRecipeParser:
    def __init__(self):
        # Support both env var names (some deployments use OPEN_API_KEY).
        self.api_key = os.environ.get('OPENAI_API_KEY') or os.environ.get('OPEN_API_KEY')
        self.client = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)

    def parse_image(self, image_file):
        try:
            # Read bytes once and detect actual format (content_type can be wrong/missing).
            try:
                image_file.seek(0)
            except Exception:
                pass
            raw_bytes = image_file.read()
            content_type = getattr(image_file, "content_type", "") or ""

            def detect_mime(data: bytes) -> tuple[str, str]:
                if not data:
                    return "application/octet-stream", "empty"
                if data.startswith(b"\x89PNG\r\n\x1a\n"):
                    return "image/png", "png"
                if data.startswith(b"\xff\xd8\xff"):
                    return "image/jpeg", "jpeg"
                if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
                    return "image/gif", "gif"
                if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
                    return "image/webp", "webp"
                # HEIC/HEIF often contains ftyp brand markers.
                if b"ftypheic" in data[:32] or b"ftypheif" in data[:32] or b"ftypmif1" in data[:32]:
                    return "image/heic", "heic"
                return "application/octet-stream", "unknown"

            detected_mime, detected_format = detect_mime(raw_bytes)
            logger.info(
                "OCR input diagnostics: content_type=%s detected_format=%s size_bytes=%s",
                content_type or "(missing)",
                detected_format,
                len(raw_bytes) if raw_bytes is not None else 0,
            )

            # If we got an unknown/unsupported type but Pillow can load it, convert to PNG.
            data_for_model = raw_bytes
            mime = detected_mime
            if detected_format in {"unknown", "empty"} and raw_bytes:
                try:
                    from PIL import Image

                    img = Image.open(BytesIO(raw_bytes))
                    out = BytesIO()
                    img.save(out, format="PNG")
                    data_for_model = out.getvalue()
                    mime = "image/png"
                    logger.info("OCR input converted to PNG via Pillow (orig_content_type=%s)", content_type or "(missing)")
                except Exception:
                    # Keep original bytes; OpenAI might still accept.
                    pass

            # Encode image to base64
            base64_image = base64.b64encode(data_for_model).decode("utf-8")
            
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
            logger.warning("OpenAI OCR error: %s", e)
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
