from __future__ import annotations

import json
import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup


def parse_iso_duration(duration_str: str | None) -> int:
    """Parse ISO 8601 duration string (e.g., PT1H30M) to minutes."""
    if not duration_str:
        return 0
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", str(duration_str))
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes


def extract_json_ld(soup: BeautifulSoup):
    """Extract recipe data from JSON-LD."""
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
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
                if node_type == 'Recipe' or (isinstance(node_type, list) and 'Recipe' in node_type):
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
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

    title = soup.title.string.strip() if soup.title and soup.title.string else ''
    description = ''
    ingredients: list[str] = []
    steps: list[str] = []
    cooking_time = 0
    servings = 4
    image_url: str | None = None

    recipe_data = extract_json_ld(soup)
    if recipe_data:
        title = str(recipe_data.get('name') or title).strip()
        description = str(recipe_data.get('description') or '').strip()

        raw_ingredients = recipe_data.get('recipeIngredient', [])
        if isinstance(raw_ingredients, list):
            ingredients = [str(i).strip() for i in raw_ingredients if str(i).strip()]
        elif isinstance(raw_ingredients, str):
            ingredients = [raw_ingredients.strip()] if raw_ingredients.strip() else []

        raw_instructions = recipe_data.get('recipeInstructions', [])
        steps = flatten_instruction_texts(raw_instructions)

        total_time = recipe_data.get('totalTime')
        cook_time = recipe_data.get('cookTime')
        prep_time = recipe_data.get('prepTime')
        if total_time:
            cooking_time = parse_iso_duration(str(total_time))
        elif cook_time or prep_time:
            cooking_time = parse_iso_duration(str(cook_time)) + parse_iso_duration(str(prep_time))

        yield_data = recipe_data.get('recipeYield')
        if yield_data:
            if isinstance(yield_data, list) and yield_data:
                yield_data = yield_data[0]
            match = re.search(r'(\d+)', str(yield_data))
            if match:
                servings = int(match.group(1))

        img_data = recipe_data.get('image')
        if isinstance(img_data, list):
            image_url = str(img_data[0]) if img_data else None
        elif isinstance(img_data, dict):
            image_url = str(img_data.get('url') or '') or None
        elif isinstance(img_data, str):
            image_url = img_data

    else:
        og_image = soup.find('meta', property='og:image')
        if og_image:
            image_url = og_image.get('content', '') or None

        og_description = soup.find('meta', property='og:description')
        if og_description:
            description = og_description.get('content', '')

        og_title = soup.find('meta', property='og:title')
        if og_title:
            ogt = og_title.get('content', '')
            if not title or title.lower() in ['instagram', 'facebook', 'log in']:
                title = ogt
                if ' on Instagram: "' in title:
                    parts = title.split(' on Instagram: "')
                    if len(parts) > 1:
                        caption = parts[1].rstrip('"')
                        title = caption.split('\n')[0][:100]
                        if not description:
                            description = caption

        if not description:
            paragraphs = [p.get_text().strip() for p in soup.find_all('p') if len(p.get_text().strip()) > 30]
            description = '\n\n'.join(paragraphs[:3])

    title = (title or '').strip()
    if not title:
        title = 'Importerad länk'

    description = (description or '').strip()
    if description:
        description = f"{description[:1000]}\n\n(Importerad från: {url})"
    else:
        description = f"(Importerad från: {url})"

    if cooking_time <= 0:
        cooking_time = 30

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
