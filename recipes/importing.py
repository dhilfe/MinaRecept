from __future__ import annotations

import json
import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup


def parse_duration(duration_input: str | int | None) -> int:
    """
    Parse duration from ISO 8601 string (PT1H30M), integer minutes, or simple text.
    Returns total minutes.
    """
    if not duration_input:
        return 0
    
    # 1. Handle integer/string-integer (assumed minutes)
    if isinstance(duration_input, int):
        return duration_input
    
    s = str(duration_input).strip().upper()
    if s.isdigit():
        return int(s)

    # 2. Handle ISO 8601 (PT1H30M)
    # Mathem example: "PT60M"
    iso_match = re.match(r"^P?T(?:(\d+)H)?(?:(\d+)M)?", s)
    if iso_match and "T" in s:
        hours = int(iso_match.group(1) or 0)
        minutes = int(iso_match.group(2) or 0)
        return hours * 60 + minutes

    # 3. Handle simple text "1 h 30 min", "90 min"
    # Extract all numbers
    # Strategy: if "h" or "tim" follows a number -> hours. if "m" or "min" -> minutes.
    # Fallback: if just one number found, assume minutes?
    
    total_minutes = 0
    # Find "X h" or "X tim"
    hours_match = re.search(r'(\d+)\s*(?:h|tim)', s, re.IGNORECASE)
    if hours_match:
        total_minutes += int(hours_match.group(1)) * 60
    
    # Find "Y m" or "Y min"
    minutes_match = re.search(r'(\d+)\s*(?:m|min)', s, re.IGNORECASE)
    if minutes_match:
        total_minutes += int(minutes_match.group(1))
    
    if total_minutes > 0:
        return total_minutes

    # Fallback: find first number and assume minutes
    simple_match = re.search(r'(\d+)', s)
    if simple_match:
        return int(simple_match.group(1))

    return 0


def extract_json_ld(soup: BeautifulSoup):
    """Extract recipe data from JSON-LD."""
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            if not script.string:
                continue
            data = json.loads(script.string)
            nodes = []
            if isinstance(data, dict):
                if '@graph' in data:
                    nodes = data['@graph']
                else:
                    nodes = [data]
            elif isinstance(data, list):
                nodes = data

            for node in nodes:
                if not isinstance(node, dict):
                    continue
                node_type = node.get('@type')
                
                # Check for "Recipe" or ["Recipe", "SomethingElse"]
                is_recipe = False
                if isinstance(node_type, str) and 'Recipe' in node_type:
                    is_recipe = True
                elif isinstance(node_type, list) and 'Recipe' in node_type:
                    is_recipe = True
                
                if is_recipe:
                    return node
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def flatten_instruction_texts(node) -> list[str]:
    """Flatten JSON-LD recipeInstructions into a list of step strings."""
    steps: list[str] = []

    def add_text(value):
        if value is None:
            return
        if isinstance(value, str):
            v = value.strip()
            # Remove HTML tags if present (e.g. <p>)
            v = re.sub(r'<[^>]+>', '', v)
            if v:
                steps.append(v)
            return
        if isinstance(value, list):
            for item in value:
                add_text(item)
            return
        if isinstance(value, dict):
            if 'text' in value:
                add_text(value.get('text'))
                return
            if 'itemListElement' in value:
                add_text(value.get('itemListElement'))
                return
            for key in ('name', 'description'):
                if key in value:
                    add_text(value.get(key))
                    return

    add_text(node)
    return [s for s in steps if s]


@dataclass(frozen=True)
class ImportedRecipeData:
    title: str
    description: str
    ingredients: list[str]
    steps: list[str]
    cooking_time: int
    servings: int
    image_url: str | None = None


def _normalize_url(url: str) -> str:
    url = (url or '').strip()
    if not url:
        return ''
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url


def fetch_html(url: str, timeout: int = 10) -> tuple[str, bytes]:
    """Fetch URL content with a www retry. Returns (final_url, content)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7'
    }

    def fetch(fetch_url: str) -> requests.Response:
        resp = requests.get(fetch_url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp

    try:
        resp = fetch(url)
        return url, resp.content
    except requests.RequestException as e:
        if 'www.' not in url:
            try:
                scheme, rest = url.split('://', 1)
                url_www = f"{scheme}://www.{rest}"
                resp2 = fetch(url_www)
                return url_www, resp2.content
            except requests.RequestException:
                pass
        raise e


def import_recipe_from_html(url: str, content: bytes) -> ImportedRecipeData:
    soup = BeautifulSoup(content, 'html.parser')

    def clean_title(raw_title: str) -> str:
        t = (raw_title or '').strip()
        if not t:
            return ''
        # Often sites put " | Brand" at the end
        if '|' in t:
            t = t.split('|', 1)[0].strip()
        # Mathem sometimes puts " - Mathem"
        if ' - ' in t:
             t = t.rsplit(' - ', 1)[0].strip()
        return t

    title = clean_title(soup.title.string) if soup.title and soup.title.string else ''
    description = ''
    ingredients: list[str] = []
    steps: list[str] = []
    cooking_time = 0
    servings = 4
    image_url: str | None = None

    # Try to find OG image first as fallback/priority if JSON-LD fails
    og_image_url = None
    og_image = soup.find('meta', property='og:image')
    if og_image:
        og_image_url = og_image.get('content', '') or None

    recipe_data = extract_json_ld(soup)
    if recipe_data:
        ld_title = clean_title(str(recipe_data.get('name') or ''))
        if ld_title:
            title = ld_title
            
        description = str(recipe_data.get('description') or '').strip()

        # Ingredients
        raw_ingredients = recipe_data.get('recipeIngredient', [])
        if isinstance(raw_ingredients, list):
            ingredients = [str(i).strip() for i in raw_ingredients if str(i).strip()]
        elif isinstance(raw_ingredients, str):
            ingredients = [raw_ingredients.strip()] if raw_ingredients.strip() else []

        # Instructions
        raw_instructions = recipe_data.get('recipeInstructions', [])
        steps = flatten_instruction_texts(raw_instructions)

        # Time
        total_time = recipe_data.get('totalTime')
        cook_time = recipe_data.get('cookTime')
        prep_time = recipe_data.get('prepTime')
        
        if total_time:
            cooking_time = parse_duration(total_time)
        elif cook_time or prep_time:
            cooking_time = parse_duration(cook_time) + parse_duration(prep_time)

        # Servings
        yield_data = recipe_data.get('recipeYield')
        if yield_data:
            # Handle list ["4 portions"] or string "4 portions"
            if isinstance(yield_data, list) and yield_data:
                yield_data = yield_data[0]
            
            y_str = str(yield_data)
            match = re.search(r'(\d+)', y_str)
            if match:
                servings = int(match.group(1))

        # Image from JSON-LD
        img_data = recipe_data.get('image')
        if isinstance(img_data, list):
            # Often contains multiple aspect ratios, pick first
            first_img = img_data[0]
            if isinstance(first_img, dict):
                 image_url = str(first_img.get('url') or '') or None
            else:
                 image_url = str(first_img)
        elif isinstance(img_data, dict):
            image_url = str(img_data.get('url') or '') or None
        elif isinstance(img_data, str):
            image_url = img_data

    # Fallback logic if JSON-LD missing or incomplete

    # 1. Image fallback (OG is often better than JSON-LD thumbnail)
    if not image_url and og_image_url:
        image_url = og_image_url
    
    # Sometimes JSON-LD has a tiny/bad image, and OG is high-res. 
    # For Mathem, OG image is usually good.
    if og_image_url and ('mathem' in url or not image_url):
         image_url = og_image_url

    # 2. Description fallback
    if not description:
        og_description = soup.find('meta', property='og:description')
        if og_description:
            description = og_description.get('content', '')

    # 3. Title fallback (OG title)
    if not title:
        og_title = soup.find('meta', property='og:title')
        if og_title:
            title = clean_title(og_title.get('content', ''))

    # Final cleanup
    title = clean_title(title)
    if not title:
        title = 'Importerad länk'

    description = (description or '').strip()
    if description:
        description = f"{description[:1000]}"

    if cooking_time <= 0:
        cooking_time = 30  # Default to 30 min if unknown

    return ImportedRecipeData(
        title=title,
        description=description,
        ingredients=ingredients,
        steps=steps,
        cooking_time=cooking_time,
        servings=servings,
        image_url=image_url,
    )


def import_recipe_from_url(url: str) -> ImportedRecipeData:
    url = _normalize_url(url)
    if not url:
        raise ValueError('Missing url')

    final_url, content = fetch_html(url)
    return import_recipe_from_html(final_url, content)
