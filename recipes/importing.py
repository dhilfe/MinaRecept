from __future__ import annotations

import json
import re
import html
from dataclasses import dataclass, replace

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
    """Extract best matching recipe data from JSON-LD.

    Many sites (incl. Coop) wrap the Recipe inside other nodes (WebPage.mainEntity, @graph, etc),
    or include multiple Recipe-like objects. We collect candidates recursively and pick the best one.
    """

    def is_recipe_type(t) -> bool:
        if isinstance(t, str):
            return "Recipe" in t
        if isinstance(t, list):
            return any(isinstance(x, str) and "Recipe" in x for x in t)
        return False

    def collect_recipe_candidates(obj) -> list[dict]:
        out: list[dict] = []
        if isinstance(obj, dict):
            if is_recipe_type(obj.get("@type")):
                out.append(obj)
            for v in obj.values():
                out.extend(collect_recipe_candidates(v))
        elif isinstance(obj, list):
            for item in obj:
                out.extend(collect_recipe_candidates(item))
        return out

    def score_recipe(node: dict) -> int:
        score = 0
        if node.get("name"):
            score += 3
        if node.get("image"):
            score += 2
        ing = node.get("recipeIngredient")
        if isinstance(ing, list):
            score += min(len(ing), 10)
        elif isinstance(ing, str) and ing.strip():
            score += 2
        instr = node.get("recipeInstructions")
        if instr:
            score += 5
        if node.get("totalTime") or node.get("cookTime") or node.get("prepTime"):
            score += 1
        return score

    scripts = soup.find_all("script", type="application/ld+json")
    candidates: list[dict] = []

    for script in scripts:
        try:
            raw = script.string
            if not raw:
                continue
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        # Normalize to a list of roots
        roots: list = []
        if isinstance(data, dict):
            roots = [data]
            if isinstance(data.get("@graph"), list):
                roots.extend(data["@graph"])
        elif isinstance(data, list):
            roots = data

        for root in roots:
            candidates.extend(collect_recipe_candidates(root))

    if not candidates:
        return None

    # Pick the best candidate (highest score)
    best = max(candidates, key=score_recipe)
    return best


def clean_text(text: str) -> str:
    """Clean text from HTML entities, tags and whitespace."""
    if not text:
        return ""
    # 1. Unescape HTML entities (&lt; -> <, &nbsp; -> space)
    text = html.unescape(text)
    # 2. Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # 3. Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def flatten_instruction_texts(node) -> list[str]:
    """Flatten JSON-LD recipeInstructions into a list of step strings."""
    steps: list[str] = []

    def add_text(value):
        if value is None:
            return
        if isinstance(value, str):
            v = clean_text(value)
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


def _extract_coop_recipe_id(html_bytes: bytes) -> str | None:
    """Best-effort: extract Coop recipe id from the HTML.

    Coop pages are often client-rendered, but the initial HTML usually contains a recipe id
    for analytics or bootstrapping.
    """
    try:
        s = html_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return None

    patterns = [
        # Common: analytics URL query param (e.g. ...&ep.recipe_id=5439115&...)
        r'ep\.recipe_id=(\d+)',
        # Sometimes URL-encoded
        r'ep\.recipe_id%3D(\d+)',
        # Assignment-style
        r'ep\.recipe_id\s*=\s*(\d+)',
        r'ep\.recipe_id\s*=\s*"(\d+)"',
        r'"recipe_id"\s*:\s*"(\d+)"',
        r'"recipe_id"\s*:\s*(\d+)',
        r'"recipeId"\s*:\s*"(\d+)"',
        r'"recipeId"\s*:\s*(\d+)',
        r'recipe[_-]?id\s*[:=]\s*"(\d+)"',
        r'recipe[_-]?id\s*[:=]\s*(\d+)',
    ]
    for p in patterns:
        m = re.search(p, s, re.IGNORECASE)
        if m:
            return m.group(1)

    # Last resort: look for "recipe_id" nearby and grab digits
    # Handles cases like "recipe_id=5439115" inside long URLs or encoded blobs.
    m2 = re.search(r"recipe[_\.]?id[^0-9]{0,20}(\d{4,12})", s, re.IGNORECASE)
    if m2:
        return m2.group(1)
    return None


def _fetch_coop_recipe_json(recipe_id: str, timeout: int = 15) -> dict | None:
    """Fetch Coop recipe JSON via their public proxy API."""
    api_url = f"https://proxy.api.coop.se/external/recipe/recipes/{recipe_id}?api-version=v1"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Origin": "https://www.coop.se",
        "Referer": "https://www.coop.se/",
    }
    try:
        resp = requests.get(api_url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _parse_coop_recipe_json(data: dict) -> ImportedRecipeData | None:
    """Parse Coop recipe JSON into our ImportedRecipeData structure (best-effort)."""
    title = clean_text(str(data.get("name") or data.get("title") or data.get("recipeName") or ""))
    if not title:
        return None

    description = clean_text(str(data.get("description") or data.get("summary") or data.get("preamble") or ""))

    def _fmt_qty(value: object) -> str:
        """Format Coop quantities like '8.0' -> '8' while keeping real decimals."""
        if value is None:
            return ""
        if isinstance(value, (int,)):
            return str(value)
        if isinstance(value, float):
            return str(int(value)) if value.is_integer() else str(value)
        s = clean_text(str(value))
        if not s:
            return ""
        # Common Coop format: "8.0"
        m = re.fullmatch(r"(\d+)\.0+", s)
        if m:
            return m.group(1)
        return s

    # Image
    image_url: str | None = None
    for k in ("imageUrl", "image_url", "heroImageUrl", "hero_image_url"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            image_url = v.strip()
            break
    if not image_url and isinstance(data.get("images"), list) and data["images"]:
        first = data["images"][0]
        if isinstance(first, dict):
            image_url = (first.get("url") or first.get("src") or None)
        elif isinstance(first, str):
            image_url = first

    # Time / servings
    cooking_time = 0
    for k in ("cookingTimeMinutes", "totalTimeMinutes", "totalTime", "cookTime", "prepTime"):
        v = data.get(k)
        if v:
            cooking_time = max(cooking_time, parse_duration(v))
    servings = 4
    for k in ("servings", "portions", "portionCount", "recipeYield"):
        v = data.get(k)
        if isinstance(v, int):
            servings = v
            break
        if isinstance(v, str):
            m = re.search(r"(\d+)", v)
            if m:
                servings = int(m.group(1))
                break

    def _parse_ingredient_list(raw) -> list[str]:
        out: list[str] = []
        if not isinstance(raw, list):
            return out
        for item in raw:
            if isinstance(item, str):
                t = clean_text(item)
                if t:
                    out.append(t)
                continue
            if isinstance(item, dict):
                # Common shapes:
                # { "name": "...", "amount": "...", "unit": "..." }
                # { "ingredient": { "name": "..." }, "quantity": "...", "unit": "..." }
                ing_obj = item.get("ingredient") if isinstance(item.get("ingredient"), dict) else None
                name = clean_text(str(item.get("name") or item.get("title") or (ing_obj.get("name") if ing_obj else "") or ""))
                amount = clean_text(str(item.get("amount") or item.get("quantity") or item.get("value") or ""))
                unit = clean_text(str(item.get("unit") or item.get("unitName") or ""))
                parts = [p for p in [amount, unit, name] if p]
                line = " ".join(parts).strip()
                if line:
                    out.append(line)
                continue
            t = clean_text(str(item))
            if t:
                out.append(t)
        return out

    # Ingredients
    ingredients: list[str] = []
    raw_ing = data.get("ingredients") or data.get("recipeIngredients") or data.get("ingredientLines") or []
    ingredients = _parse_ingredient_list(raw_ing)

    # Coop sometimes stores ingredients per "recipe part" keys like "recipePart-0-ingredients"
    if not ingredients:
        for k, v in data.items():
            if isinstance(k, str) and "recipepart-" in k.lower() and "ingredients" in k.lower():
                ingredients = _parse_ingredient_list(v)
                if ingredients:
                    break

    # Coop can also store recipe parts as a list: recipePart: [{..., ingredients: [...]}, ...]
    if not ingredients and isinstance(data.get("recipePart"), list):
        for part in data.get("recipePart") or []:
            if not isinstance(part, dict):
                continue
            part_ings = part.get("ingredients")
            if isinstance(part_ings, list) and part_ings:
                # ingredient objects often have: name, quantity, unit
                for item in part_ings:
                    if isinstance(item, dict):
                        name = clean_text(str(item.get("name") or item.get("ingredientName") or ""))
                        qty = _fmt_qty(item.get("quantity") or item.get("amount"))
                        unit = clean_text(str(item.get("unit") or item.get("unitName") or ""))
                        parts = [p for p in [qty, unit, name] if p]
                        line = " ".join(parts).strip()
                        if line:
                            ingredients.append(line)
                    elif isinstance(item, str):
                        t = clean_text(item)
                        if t:
                            ingredients.append(t)
            if ingredients:
                break

    # Steps
    steps: list[str] = []
    raw_steps = (
        data.get("instructions")
        or data.get("steps")
        or data.get("method")
        or data.get("recipeInstructions")
        or data.get("cookingInstructions")
        or data.get("cookingInstruction")
        or data.get("directions")
        or data.get("preparation")
        or []
    )
    if isinstance(raw_steps, str):
        s = clean_text(raw_steps)
        if s:
            steps = [s]
    elif isinstance(raw_steps, list):
        for item in raw_steps:
            if isinstance(item, str):
                t = clean_text(item)
                if t:
                    steps.append(t)
            elif isinstance(item, dict):
                t = clean_text(str(item.get("text") or item.get("description") or item.get("instruction") or ""))
                if t:
                    steps.append(t)

    # Coop sometimes stores steps per "recipe part" keys too, e.g. "recipePart-0-instructions"
    if not steps:
        for k, v in data.items():
            if not (isinstance(k, str) and "recipepart-" in k.lower()):
                continue
            if "instructions" in k.lower() or "steps" in k.lower() or "method" in k.lower():
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, str):
                            t = clean_text(item)
                            if t:
                                steps.append(t)
                        elif isinstance(item, dict):
                            t = clean_text(str(item.get("text") or item.get("description") or item.get("instruction") or ""))
                            if t:
                                steps.append(t)
                elif isinstance(v, str):
                    t = clean_text(v)
                    if t:
                        steps.append(t)
                if steps:
                    break

    # Coop can also store instructions within recipePart list objects
    if not steps and isinstance(data.get("recipePart"), list):
        for part in data.get("recipePart") or []:
            if not isinstance(part, dict):
                continue
            # Try common keys first
            part_steps = (
                part.get("instructions")
                or part.get("steps")
                or part.get("method")
                or part.get("recipeInstructions")
                or part.get("cookingInstructions")
                or part.get("cookingInstruction")
            )

            # Fallback: scan any keys containing instruction/step/method
            if not part_steps:
                for k, v in part.items():
                    if not isinstance(k, str):
                        continue
                    lk = k.lower()
                    if "instruction" in lk or "step" in lk or "method" in lk or "howto" in lk:
                        part_steps = v
                        break

            if isinstance(part_steps, str):
                t = clean_text(part_steps)
                if t:
                    steps.append(t)
            elif isinstance(part_steps, list):
                for item in part_steps:
                    if isinstance(item, str):
                        t = clean_text(item)
                        if t:
                            steps.append(t)
                    elif isinstance(item, dict):
                        t = clean_text(str(item.get("text") or item.get("description") or item.get("instruction") or ""))
                        if t:
                            steps.append(t)
            if steps:
                break

    # Coop may also deliver instructions in a separate top-level array linked to recipePartId
    if not steps:
        for key in (
            "recipePartInstructions",
            "recipePartInstruction",
            "instructions",
            "instructionSteps",
            "preparationSteps",
            "cookingInstructions",
            "cookingInstruction",
            "directions",
        ):
            blob = data.get(key)
            if not blob:
                continue
            if isinstance(blob, list):
                for item in blob:
                    if isinstance(item, str):
                        t = clean_text(item)
                        if t:
                            steps.append(t)
                    elif isinstance(item, dict):
                        t = clean_text(str(item.get("text") or item.get("description") or item.get("instruction") or item.get("name") or ""))
                        if t:
                            steps.append(t)
            elif isinstance(blob, str):
                t = clean_text(blob)
                if t:
                    steps.append(t)
            if steps:
                break

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


def _normalize_url(url: str) -> str:
    url = (url or '').strip()
    if not url:
        return ''
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Special handling for ICA app links: ?recipeid=XXXXXX
    # Redirects to /recept/XXXXXX/ which then 301 redirects to the correct slug-URL.
    if 'ica.se' in url and 'recipeid=' in url:
        match = re.search(r'recipeid=(\d+)', url)
        if match:
             recipe_id = match.group(1)
             return f"https://www.ica.se/recept/{recipe_id}/"

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
        t = clean_text(raw_title)
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
            
        description = clean_text(str(recipe_data.get('description') or ''))

        # Ingredients (string | list[str] | list[dict])
        raw_ingredients = recipe_data.get('recipeIngredient', [])
        if isinstance(raw_ingredients, list):
            parsed: list[str] = []
            for item in raw_ingredients:
                if isinstance(item, str):
                    t = clean_text(item)
                    if t:
                        parsed.append(t)
                elif isinstance(item, dict):
                    # Some sites use {"text": "..."} or {"name": "..."}
                    t = clean_text(str(item.get("text") or item.get("name") or item.get("value") or ""))
                    if t:
                        parsed.append(t)
                else:
                    t = clean_text(str(item))
                    if t:
                        parsed.append(t)
            ingredients = parsed
        elif isinstance(raw_ingredients, str):
            ingredients = [clean_text(raw_ingredients)] if raw_ingredients.strip() else []

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
    
    # 4. Fallback for Kokaihop: ingredients from meta keywords
    def _extract_kokaihop_friendly_url(raw_url: str) -> str | None:
        # Example:
        # https://www.kokaihop.se/recept/bacon-och-rodlokssnittar
        match = re.search(r"/recept/([^/?#]+)", raw_url)
        return match.group(1) if match else None

    def _fetch_kokaihop_recipe_via_graphql(friendly_url: str, timeout: int = 15) -> ImportedRecipeData | None:
        """
        Kokaihop is client-rendered: HTML often has empty <ul></ul>/<ol></ol>.
        However, the site exposes a public GraphQL endpoint we can call:
          POST https://www.kokaihop.se/graphql
          showRecipe(friendlyUrl: ...)
        """
        gql_url = "https://www.kokaihop.se/graphql"
        query = """
        query ($friendlyUrl: String!) {
          showRecipe(friendlyUrl: $friendlyUrl, sendUserEvents: false, changeDescField: true) {
            statusCode
            error
            data {
              title
              recipeDescription
              description { short long }
              servings
              totalTime
              cookingTime
              preparationTime
              ovenTime
              ingredients { isHeader name amount unit { name } }
              cookingSteps
            }
          }
        }
        """
        payload = {"query": query, "variables": {"friendlyUrl": friendly_url}}
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": f"https://www.kokaihop.se/recept/{friendly_url}",
        }
        try:
            resp = requests.post(gql_url, json=payload, headers=headers, timeout=timeout)
            resp.raise_for_status()
            body = resp.json()
        except Exception:
            return None

        show = ((body or {}).get("data") or {}).get("showRecipe") or {}
        data = show.get("data") or {}
        if not isinstance(data, dict):
            return None

        gql_title = clean_title(str(data.get("title") or ""))
        if not gql_title:
            return None

        gql_description = clean_text(
            str(
                data.get("recipeDescription")
                or ((data.get("description") or {}) if isinstance(data.get("description"), dict) else {}).get("long")
                or ((data.get("description") or {}) if isinstance(data.get("description"), dict) else {}).get("short")
                or ""
            )
        )

        gql_ingredients: list[str] = []
        raw_ings = data.get("ingredients")
        if isinstance(raw_ings, list):
            for ing in raw_ings:
                if not isinstance(ing, dict):
                    continue
                if ing.get("isHeader") is True:
                    header = clean_text(str(ing.get("name") or ""))
                    if header:
                        gql_ingredients.append(header)
                    continue

                name = clean_text(str(ing.get("name") or ""))
                amount = clean_text(str(ing.get("amount") or ""))
                unit = ""
                if isinstance(ing.get("unit"), dict):
                    unit = clean_text(str(ing["unit"].get("name") or ""))
                parts = [p for p in [amount, unit, name] if p]
                line = " ".join(parts).strip()
                if line:
                    gql_ingredients.append(line)

        gql_steps: list[str] = []
        raw_steps = data.get("cookingSteps")
        if isinstance(raw_steps, list):
            for s in raw_steps:
                t = clean_text(str(s or ""))
                if t:
                    gql_steps.append(t)

        cooking_time = 0
        for k in ("totalTime", "cookingTime", "preparationTime", "ovenTime"):
            v = data.get(k)
            if isinstance(v, int) and v > 0:
                cooking_time = max(cooking_time, v)

        servings = 4
        servings_raw = data.get("servings") or ""
        m = re.search(r"(\d+)", str(servings_raw))
        if m:
            servings = int(m.group(1))

        return ImportedRecipeData(
            title=gql_title,
            description=gql_description,
            ingredients=gql_ingredients,
            steps=gql_steps,
            cooking_time=cooking_time if cooking_time > 0 else 30,
            servings=servings,
            image_url=None,
        )

    if "kokaihop.se" in url and (not ingredients or not steps):
        friendly_url = _extract_kokaihop_friendly_url(url)
        if friendly_url:
            kokaihop_data = _fetch_kokaihop_recipe_via_graphql(friendly_url)
            if kokaihop_data and (kokaihop_data.ingredients or kokaihop_data.steps):
                # Keep the best image we already found (OG is usually great for Kokaihop)
                return replace(kokaihop_data, image_url=(image_url or og_image_url))

    if not ingredients and "kokaihop.se" in url:
        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        if meta_keywords:
            content_str = meta_keywords.get("content", "")
            # Filter out generic keywords
            ignore_words = {
                "mat",
                "recept",
                "matrecept",
                "receptbilder",
                "hitta recept",
                "kokaihop",
                "kokaihop.se",
                title.lower(),
            }

            raw_list = [w.strip() for w in content_str.split(",")]
            for w in raw_list:
                if w and w.lower() not in ignore_words:
                    ingredients.append(w)

    # 5. Generic HTML fallback for ingredients/steps (helps when JSON-LD is missing/blocked)
    def _extract_list_after_heading(keywords: list[str], list_tag: str) -> list[str]:
        # Find headings or strong labels matching any keyword (word-boundary where possible),
        # then grab the next list. This avoids false positives like "Hitta recept efter ingrediens".
        lowered = [k.lower() for k in keywords]
        patterns: list[re.Pattern] = []
        for k in lowered:
            # For single-word keywords, require word boundary.
            if re.match(r"^[a-zåäö]+$", k, re.IGNORECASE):
                patterns.append(re.compile(rf"\b{re.escape(k)}\b", re.IGNORECASE))
            else:
                patterns.append(re.compile(re.escape(k), re.IGNORECASE))
        for el in soup.find_all(["h1", "h2", "h3", "h4", "strong", "p", "span", "div"]):
            text = clean_text(el.get_text(" ", strip=True)).lower()
            if not text:
                continue
            if not any(p.search(text) for p in patterns):
                continue
            # Search next elements for a list
            next_list = el.find_next(list_tag)
            if next_list:
                items = [clean_text(li.get_text(" ", strip=True)) for li in next_list.find_all("li")]
                return [i for i in items if i]
        return []

    # 5b. Landleyskok-specific fallback:
    # Their pages often have long article text and the recipe section far down (anchor #recept-content),
    # and menu text includes "Hitta recept efter ingrediens" which can trick generic heading matching.
    if "landleyskok.se" in url:
        scope = soup
        scope_el = soup.select_one("#recept-content")
        if scope_el is not None:
            scope = scope_el

        # Prefer the actual recipe title from "Recept på X" if present inside the recipe section.
        # (Article title can be "Så enkelt är det att göra ...", which is not the recipe name.)
        if scope is not None:
            # Avoid regex over the whole scope text (which may collapse newlines) – find the actual heading node.
            for h in scope.find_all(["h1", "h2", "h3", "h4"]):
                t = clean_text(h.get_text(" ", strip=True))
                m = re.search(r"\bRecept\s+p[åa]\s+(.+)$", t, re.IGNORECASE)
                if m:
                    possible = clean_title(m.group(1))
                    if possible:
                        title = possible
                        break

        def looks_like_nav(lines: list[str]) -> bool:
            if not lines:
                return False
            # Nav/menu items typically have no quantities.
            digits = sum(1 for x in lines if re.search(r"\d", x))
            return digits == 0

        def choose_best_ingredient_list(root) -> list[str]:
            candidates: list[list[str]] = []
            for ul in root.find_all("ul"):
                items = [clean_text(li.get_text(" ", strip=True)) for li in ul.find_all("li")]
                items = [x for x in items if x]
                if len(items) < 3:
                    continue
                # Heuristic: ingredient lists usually contain digits/units in many lines.
                score = sum(1 for x in items if re.search(r"\d", x))
                if score == 0:
                    continue
                candidates.append(items)

            if not candidates:
                return []

            # Choose the list with highest "digit-line" count.
            candidates.sort(key=lambda lst: sum(1 for x in lst if re.search(r"\d", x)), reverse=True)
            best = candidates[0]
            return best

        def extract_quantity_lines(root) -> list[str]:
            """
            Landleys sometimes uses checkbox-style markup, not <li>. Extract ingredient-like lines by pattern.
            """
            unit_words = [
                "kg", "g", "mg",
                "l", "dl", "cl", "ml",
                "msk", "tsk", "krm",
                "st", "styck", "stycken",
                "port", "portion", "portioner",
            ]
            unit_re = re.compile(rf"\b(?:{'|'.join(map(re.escape, unit_words))})\b", re.IGNORECASE)

            bad_snippets = [
                "receptgeneratorn",
                "hitta recept efter ingrediens",
                "mina sparade recept",
                "om landleys",
            ]

            out: list[str] = []
            for el in root.find_all(["label", "li", "p", "span", "div"]):
                t = clean_text(el.get_text(" ", strip=True))
                if not t:
                    continue
                tl = t.lower()
                if any(b in tl for b in bad_snippets):
                    continue
                # Must contain a digit and ideally a unit word.
                if not re.search(r"\d", t):
                    continue
                if not unit_re.search(t):
                    # Still allow some common patterns like "33 cl" (unit handled) or "0,5 tsk" etc.
                    # If no unit, likely not an ingredient.
                    continue
                # Skip obvious temperatures/times.
                # IMPORTANT: don't treat ingredient words like "spiskummin" as time ("min").
                if "°" in t or "grader" in tl:
                    continue
                if re.search(r"\b(min|minuter|tim|timmar)\b", tl):
                    continue
                if len(t) > 140:
                    continue
                out.append(t)

            # Deduplicate while preserving order
            seen = set()
            deduped: list[str] = []
            for x in out:
                if x in seen:
                    continue
                seen.add(x)
                deduped.append(x)
            return deduped

        # If ingredients are missing or clearly came from nav/menu, try to extract from recipe section.
        if looks_like_nav(ingredients):
            ingredients = []

        if not ingredients:
            try:
                root = scope if scope is not None else soup
                extracted = choose_best_ingredient_list(root)
                if not extracted:
                    extracted = extract_quantity_lines(root)
                if extracted:
                    ingredients = extracted
            except Exception:
                pass

    if not ingredients:
        # Microdata fallback
        micro = [clean_text(x.get_text(" ", strip=True)) for x in soup.select('[itemprop="recipeIngredient"]')]
        micro = [m for m in micro if m]
        if micro:
            ingredients = micro
        else:
            # Common "recipe card" plugins used by many blogs.
            plugin_selectors = [
                # WP Recipe Maker
                ".wprm-recipe-ingredient",
                ".wprm-recipe-ingredient-name",
                # Mediavine Create
                ".mv-create-ingredients li",
                ".mv-create-ingredients-item",
                # Tasty Recipes
                ".tasty-recipes-ingredients li",
                # Generic
                ".recipe-ingredients li",
            ]
            plugin_ings: list[str] = []
            for sel in plugin_selectors:
                for el in soup.select(sel):
                    t = clean_text(el.get_text(" ", strip=True))
                    if t:
                        plugin_ings.append(t)
            # Deduplicate while preserving order
            # Guard: avoid nav lists accidentally matching generic selectors
            if plugin_ings and any(re.search(r"\d", x) for x in plugin_ings):
                seen = set()
                deduped: list[str] = []
                for x in plugin_ings:
                    if x in seen:
                        continue
                    seen.add(x)
                    deduped.append(x)
                ingredients = deduped
            else:
                ingredients = _extract_list_after_heading(["ingredienser", "det här behöver du", "du behöver"], "ul")

    if not steps:
        micro_steps = [clean_text(x.get_text(" ", strip=True)) for x in soup.select('[itemprop="recipeInstructions"]')]
        micro_steps = [m for m in micro_steps if m]
        if micro_steps:
            steps = micro_steps
        else:
            steps = _extract_list_after_heading(["gör så här", "instruktioner", "så gör du"], "ol")
            if not steps:
                # sometimes steps are in ul
                steps = _extract_list_after_heading(["gör så här", "instruktioner", "så gör du"], "ul")

    # 6. Coop API fallback (Coop is often client-side rendered; HTML lacks recipe data)
    if "coop.se" in url and (not ingredients and not steps):
        recipe_id = _extract_coop_recipe_id(content)
        if recipe_id:
            coop_json = _fetch_coop_recipe_json(recipe_id)
            coop_data = _parse_coop_recipe_json(coop_json or {}) if coop_json else None
            if coop_data and (coop_data.ingredients or coop_data.steps):
                return coop_data

    # Final cleanup
    title = clean_title(title)
    if not title:
        title = 'Importerad länk'

    description = clean_text(description)
    
    # Specific cleanup for Mathem
    if 'mathem' in url:
        # Remove common Mathem boilerplates
        description = description.replace("Det här receptet ingår i Mathems koncept", "")
        # Remove any trailing junk if needed
    
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
