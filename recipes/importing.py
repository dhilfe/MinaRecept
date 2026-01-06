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
        resp_url = getattr(resp, 'url', None)
        final_url = resp_url if isinstance(resp_url, str) and resp_url else url
        return final_url, resp.content
    except requests.RequestException as e:
        if 'www.' not in url:
            try:
                scheme, rest = url.split('://', 1)
                url_www = f"{scheme}://www.{rest}"
                resp2 = fetch(url_www)
                resp2_url = getattr(resp2, 'url', None)
                final_url = resp2_url if isinstance(resp2_url, str) and resp2_url else url_www
                return final_url, resp2.content
            except requests.RequestException:
                pass
        raise e


def import_recipe_from_html(url: str, content: bytes, source_text: str | None = None) -> ImportedRecipeData:
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

    def _is_instagram_url(u: str) -> bool:
        return 'instagram.com' in (u or '').lower()

    def _is_generic_instagram_title(t: str) -> bool:
        low = (t or '').strip().lower()
        return low in {
            '',
            'instagram',
            'log in',
            'log in • instagram',
            'login • instagram',
            'logga in',
            'logga in • instagram',
        }

    def _extract_instagram_caption(text: str) -> str:
        """Best-effort extract caption from IG og:title/og:description style strings."""
        raw = (text or '').strip()
        if not raw:
            return ''
        # Common patterns:
        #   User on Instagram: “caption ...”
        #   User on Instagram: "caption ..."
        for marker in [' on Instagram: “', ' on Instagram: "']:
            if marker in raw:
                after = raw.split(marker, 1)[1]
                after = after.rstrip('”').rstrip('"').strip()
                return after
        return raw

    def _parse_caption_to_recipe(text: str) -> tuple[list[str], list[str], str]:
        """Best-effort parse for captions (Instagram etc.)."""
        import re

        raw = (text or '').replace('\r\n', '\n').replace('\r', '\n')
        # Some sources (e.g. embed HTML) contain literal "\\n" sequences.
        raw = raw.replace('\\n', '\n')
        raw = re.sub(r"https?://\S+", "", raw)
        lines = [ln.strip() for ln in raw.split('\n') if ln.strip()]
        if not lines:
            return [], [], ''

        def is_heading(line: str) -> bool:
            l = line.strip()
            if l.endswith(":"):
                return True
            low = l.lower().strip()
            return low in {
                "ingredienser",
                "ingredients",
                "gör så här",
                "gor sa har",
                "instruktioner",
                "instructions",
                "tillagning",
            }

        def normalize_heading(line: str) -> str:
            return line.strip().rstrip(":").strip()

        ing_start = None
        step_start = None
        for i, ln in enumerate(lines):
            low = ln.lower().rstrip(":").strip()
            if ing_start is None and ("ingredien" in low or low == "ingredients"):
                ing_start = i + 1
                continue
            if step_start is None and (
                "gör" in low
                or "gor" in low
                or "instruktion" in low
                or low == "instructions"
                or "tillag" in low
            ):
                step_start = i + 1
                continue

        def collect_until_next_heading(start_idx: int | None) -> list[str]:
            if start_idx is None:
                return []
            out: list[str] = []
            for ln in lines[start_idx:]:
                if is_heading(ln):
                    break
                s = re.sub(r"^[-•*]+\s*", "", ln).strip()
                if s:
                    out.append(s)
            return out

        ing_lines = collect_until_next_heading(ing_start)
        step_lines = collect_until_next_heading(step_start)

        # If no explicit section markers, keep caption as description only.
        if not ing_lines and not step_lines:
            return [], [], raw.strip()

        # Preserve headings like "Dressing:" by keeping lines ending with ":" inside the section.
        def add_section_headings(start_idx: int | None, collected: list[str]) -> list[str]:
            if start_idx is None:
                return collected
            out: list[str] = []
            for ln in lines[start_idx:]:
                # stop at next major section heading
                if is_heading(ln) and (
                    "ingredien" in ln.lower() or "gör" in ln.lower() or "gor" in ln.lower() or "instruktion" in ln.lower()
                ):
                    break
                if ln.endswith(":") and normalize_heading(ln):
                    out.append(normalize_heading(ln) + ":")
                    continue
                if is_heading(ln):
                    break
                s = re.sub(r"^[-•*]+\s*", "", ln).strip()
                if s:
                    out.append(s)
            return out or collected

        ing_lines = add_section_headings(ing_start, ing_lines)
        step_lines = add_section_headings(step_start, step_lines)

        return ing_lines, step_lines, ''

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
    og_title = soup.find('meta', property='og:title')
    og_title_text = clean_title(og_title.get('content', '')) if og_title else ''
    if not title:
        if og_title_text:
            title = og_title_text

    # Instagram-specific improvements: IG often returns <title>Instagram</title> for logged-out users.
    if _is_instagram_url(url) and _is_generic_instagram_title(title):
        title = ''
        if og_title_text:
            title = og_title_text

    if _is_instagram_url(url):
        import logging
        import os

        logger = logging.getLogger(__name__)

        def _instagram_request_config() -> tuple[dict | None, str]:
            """Return (proxies, user_agent) for Instagram requests.

            Optional env vars:
            - INSTAGRAM_PROXY_URL: e.g. http://user:pass@host:port (used for both http/https)
            - INSTAGRAM_USER_AGENT: overrides the default desktop UA
            """
            proxy_url = (os.environ.get('INSTAGRAM_PROXY_URL') or '').strip()
            proxies = None
            if proxy_url:
                proxies = {
                    'http': proxy_url,
                    'https': proxy_url,
                }

            default_ua = (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
            ua = (os.environ.get('INSTAGRAM_USER_AGENT') or '').strip() or default_ua
            return proxies, ua

        def _get_instagram_auth_cookies() -> tuple[dict[str, str], bool]:
            """Return (cookies, has_raw_cookie_string).

            If INSTAGRAM_COOKIES is set, we parse that full Cookie header string.
            Otherwise we fall back to INSTAGRAM_SESSIONID (+ optional csrftoken/ds_user_id).
            """
            raw = (os.environ.get('INSTAGRAM_COOKIES') or '').strip()
            cookies: dict[str, str] = {}
            has_raw = bool(raw)
            if raw:
                for part in raw.split(';'):
                    part = part.strip()
                    if not part or '=' not in part:
                        continue
                    k, v = part.split('=', 1)
                    k = k.strip()
                    v = v.strip()
                    if k and v:
                        cookies[k] = v

            sessionid = (os.environ.get('INSTAGRAM_SESSIONID') or '').strip()
            if sessionid and 'sessionid' not in cookies:
                cookies['sessionid'] = sessionid

            csrftoken = (os.environ.get('INSTAGRAM_CSRFTOKEN') or '').strip()
            if csrftoken and 'csrftoken' not in cookies:
                cookies['csrftoken'] = csrftoken

            ds_user_id = (os.environ.get('INSTAGRAM_DS_USER_ID') or '').strip()
            if ds_user_id and 'ds_user_id' not in cookies:
                cookies['ds_user_id'] = ds_user_id

            return cookies, has_raw

        # Prefer OG image for reels/posts.
        if og_image_url:
            image_url = og_image_url

        # Try to extract caption from available fields.
        og_desc = soup.find('meta', property='og:description')
        og_desc_text = (og_desc.get('content', '') if og_desc else '')
        caption = _extract_instagram_caption(source_text or '')
        if not caption:
            caption = _extract_instagram_caption(og_desc_text)
        if not caption and og_title_text:
            caption = _extract_instagram_caption(og_title_text)

        did_try_oembed = False
        oembed_ok = False

        def _fetch_instagram_oembed(target_url: str) -> dict | None:
            """Fetch Instagram oEmbed (no auth) as a fallback for caption/thumbnail."""
            try:
                from urllib.parse import quote
                import logging

                logger = logging.getLogger(__name__)

                encoded = quote(target_url, safe='')
                proxies, ua = _instagram_request_config()

                # In practice, https://www.instagram.com/oembed/ tends to be more reliable than api.instagram.com
                # for unauthenticated requests.
                oembed_candidates = [
                    f"https://www.instagram.com/oembed/?url={encoded}&omitscript=true",
                    f"https://api.instagram.com/oembed/?url={encoded}&omitscript=true",
                ]

                last_status: int | None = None
                last_body: str | None = None
                last_ct: str | None = None
                last_url: str | None = None
                last_error: str | None = None

                for oembed_url in oembed_candidates:
                    try:
                        resp = requests.get(
                            oembed_url,
                            headers={
                                "User-Agent": ua,
                                "Accept": "application/json",
                            },
                            proxies=proxies,
                            timeout=10,
                        )
                        last_url = oembed_url
                        raw_status = getattr(resp, 'status_code', None)
                        status: int | None = None
                        if isinstance(raw_status, int):
                            status = raw_status
                        elif isinstance(raw_status, str) and raw_status.isdigit():
                            status = int(raw_status)
                        last_status = status
                        last_ct = (getattr(resp, 'headers', {}) or {}).get('Content-Type')

                        if status is not None and status >= 400:
                            last_body = (getattr(resp, 'text', '') or '')[:300]
                        resp.raise_for_status()

                        # Instagram sometimes returns HTML challenges/rate-limit pages with 200.
                        # Treat non-JSON as failure and log a short snippet.
                        if last_ct and 'json' not in last_ct.lower():
                            last_body = (getattr(resp, 'text', '') or '')[:300]
                            raise ValueError(f"Non-JSON oEmbed response ct={last_ct}")

                        try:
                            data = resp.json()
                        except Exception as e:
                            last_body = (getattr(resp, 'text', '') or '')[:300]
                            raise e
                        if isinstance(data, dict):
                            return data
                    except Exception as e:
                        last_error = f"{type(e).__name__}: {e}"
                        if last_body is None:
                            last_body = (getattr(resp, 'text', '') or '')[:300] if 'resp' in locals() else None
                        continue

                if last_status is not None and last_status >= 400:
                    logger.warning(
                        "Instagram oEmbed failed (status=%s ct=%s url=%s body=%s)",
                        last_status,
                        last_ct,
                        last_url,
                        (last_body or "")[:300],
                    )
                elif last_error:
                    logger.warning(
                        "Instagram oEmbed failed (%s ct=%s url=%s body=%s)",
                        last_error,
                        last_ct,
                        last_url,
                        (last_body or "")[:300],
                    )
                return None
            except Exception:
                return None

        def _try_instagram_embed_fallback(target_url: str) -> tuple[str, str, str] | None:
            """Try fetching the public /embed/ page, which often contains OG tags even when the main page doesn't."""
            try:
                import logging
                from urllib.parse import urlsplit

                logger = logging.getLogger(__name__)
                parts = urlsplit(target_url)
                path_parts = [p for p in (parts.path or '').split('/') if p]
                if len(path_parts) < 2:
                    return None
                kind = path_parts[0].lower()
                shortcode = path_parts[1]
                if kind not in {'reel', 'p', 'tv'}:
                    return None

                embed_candidates = [
                    f"https://www.instagram.com/{kind}/{shortcode}/embed/",
                    f"https://www.instagram.com/{kind}/{shortcode}/embed/captioned/",
                ]

                proxies, ua = _instagram_request_config()
                headers = {
                    "User-Agent": ua,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7",
                }

                cookies, has_raw_cookies = _get_instagram_auth_cookies()
                # Do authenticated embed attempts when we likely have a real logged-in cookie jar.
                # - Full cookie string provided, OR
                # - csrftoken provided (often required alongside sessionid for authenticated responses)
                should_try_auth_embed = bool(cookies.get('sessionid')) and (
                    has_raw_cookies or bool(cookies.get('csrftoken'))
                )

                for embed_url in embed_candidates:
                    resp = requests.get(embed_url, headers=headers, proxies=proxies, timeout=10)
                    status = getattr(resp, 'status_code', 0)
                    ct = (getattr(resp, 'headers', {}) or {}).get('Content-Type')

                    if status >= 400:
                        logger.warning(
                            "Instagram embed fetch failed (status=%s ct=%s url=%s)",
                            status,
                            ct,
                            embed_url,
                        )
                        continue

                    embed_soup = BeautifulSoup(resp.content, 'html.parser')
                    e_title = embed_soup.find('meta', property='og:title')
                    e_desc = embed_soup.find('meta', property='og:description')
                    e_img = embed_soup.find('meta', property='og:image')

                    e_title_text = clean_title(e_title.get('content', '')) if e_title else ''
                    e_desc_text = (e_desc.get('content', '') if e_desc else '')
                    e_img_url = (e_img.get('content', '') if e_img else '')

                    # Some embed variants put caption text as visible <p> content.
                    if not e_desc_text:
                        paras = [clean_text(p.get_text("\n", strip=True)) for p in embed_soup.find_all('p')]
                        paras = [p for p in paras if p]
                        if paras:
                            e_desc_text = "\n\n".join(paras)[:4000]

                    if e_title_text or e_desc_text or e_img_url:
                        return e_title_text, e_desc_text, e_img_url

                    # If public embed is a JS shell, retry once with cookies.
                    if should_try_auth_embed:
                        try:
                            auth_headers = dict(headers)
                            auth_headers['Referer'] = target_url
                            if cookies.get('csrftoken'):
                                auth_headers['X-CSRFToken'] = cookies['csrftoken']
                            auth_resp = requests.get(
                                embed_url,
                                headers=auth_headers,
                                cookies=cookies,
                                proxies=proxies,
                                timeout=10,
                            )
                            a_status = getattr(auth_resp, 'status_code', 0)
                            a_ct = (getattr(auth_resp, 'headers', {}) or {}).get('Content-Type')
                            if a_status < 400:
                                auth_soup = BeautifulSoup(auth_resp.content, 'html.parser')
                                a_title = auth_soup.find('meta', property='og:title')
                                a_desc = auth_soup.find('meta', property='og:description')
                                a_img = auth_soup.find('meta', property='og:image')
                                a_title_text = clean_title(a_title.get('content', '')) if a_title else ''
                                a_desc_text = (a_desc.get('content', '') if a_desc else '')
                                a_img_url = (a_img.get('content', '') if a_img else '')

                                if not a_desc_text:
                                    paras = [clean_text(p.get_text("\n", strip=True)) for p in auth_soup.find_all('p')]
                                    paras = [p for p in paras if p]
                                    if paras:
                                        a_desc_text = "\n\n".join(paras)[:4000]

                                if a_title_text or a_desc_text or a_img_url:
                                    logger.info(
                                        "Instagram authenticated embed succeeded (status=%s ct=%s url=%s)",
                                        a_status,
                                        a_ct,
                                        embed_url,
                                    )
                                    return a_title_text, a_desc_text, a_img_url
                                else:
                                    a_snip = (getattr(auth_resp, 'text', '') or '')[:200]
                                    logger.warning(
                                        "Instagram authenticated embed returned no OG/caption (status=%s ct=%s url=%s body=%s)",
                                        a_status,
                                        a_ct,
                                        embed_url,
                                        a_snip,
                                    )
                            else:
                                logger.warning(
                                    "Instagram authenticated embed failed (status=%s ct=%s url=%s)",
                                    a_status,
                                    a_ct,
                                    embed_url,
                                )
                        except Exception:
                            pass

                    snippet = (getattr(resp, 'text', '') or '')[:200]
                    logger.warning(
                        "Instagram embed returned no OG/caption (status=%s ct=%s url=%s body=%s)",
                        status,
                        ct,
                        embed_url,
                        snippet,
                    )

                return None
            except Exception:
                return None

        def _extract_caption_from_oembed_html(html: str) -> str:
            try:
                if not (html or '').strip():
                    return ""
                embed_soup = BeautifulSoup(html, "html.parser")
                # Instagram embed often includes caption text in <p> elements.
                texts = []
                for p in embed_soup.find_all("p"):
                    t = p.get_text("\n", strip=True)
                    t = (t or '').replace('\\n', '\n').strip()
                    if t:
                        texts.append(t)
                # Deduplicate and join.
                out = []
                seen = set()
                for t in texts:
                    if t in seen:
                        continue
                    seen.add(t)
                    out.append(t)
                return "\n\n".join(out).strip()
            except Exception:
                return ""

        # If IG HTML didn't provide useful metadata, try oEmbed.
        should_try_oembed = (
            not caption
            and (
                (not ingredients)
                or (not steps)
                or (not title)
                or _is_generic_instagram_title(title)
                or (og_title_text and ' on instagram:' in og_title_text.lower())
            )
        )

        if should_try_oembed:
            did_try_oembed = True
            oembed = _fetch_instagram_oembed(url)
            if oembed:
                oembed_ok = True
                thumb = clean_text(str(oembed.get("thumbnail_url") or ""))
                if thumb and not image_url:
                    image_url = thumb

                # oEmbed sometimes provides a title derived from caption.
                oe_title = clean_text(str(oembed.get("title") or ""))
                oe_html = str(oembed.get("html") or "")
                oe_caption = _extract_caption_from_oembed_html(oe_html)
                if not oe_caption:
                    oe_caption = oe_title

                if oe_caption:
                    caption = oe_caption

                # If title still empty, use caption first line or fallback.
                if not title or _is_generic_instagram_title(title):
                    if caption:
                        cap_first = caption.splitlines()[0].strip()
                        if cap_first:
                            title = clean_title(cap_first)[:200]
                    if not title:
                        author = clean_text(str(oembed.get("author_name") or ""))
                        title = f"Recept från {author}" if author else "Recept från Instagram"

        # If oEmbed is blocked and we still have nothing, try the public embed page.
        if not caption and not oembed_ok:
            embed = _try_instagram_embed_fallback(url)
            if embed:
                e_title_text, e_desc_text, e_img_url = embed
                if e_img_url and not image_url:
                    image_url = e_img_url
                if not caption and e_desc_text:
                    caption = _extract_instagram_caption(e_desc_text)
                if not caption and e_title_text:
                    caption = _extract_instagram_caption(e_title_text)
                if not title and e_title_text:
                    title = e_title_text

        def _extract_caption_from_instagram_json(data: object) -> tuple[str, str | None]:
            """Return (caption, image_url) from known Instagram JSON shapes."""
            try:
                if not isinstance(data, dict):
                    return '', None

                def _preserve_caption(raw: object) -> str:
                    # Keep newlines so downstream parsing (Ingredienser/Gör så här) works.
                    s = str(raw or '')
                    s = s.replace('\r\n', '\n').replace('\r', '\n')
                    s = s.replace('\xa0', ' ')
                    return s.strip()

                # Newer __a=1 responses may contain "graphql".
                graphql = data.get('graphql') if isinstance(data.get('graphql'), dict) else None
                if graphql and isinstance(graphql.get('shortcode_media'), dict):
                    media = graphql['shortcode_media']
                    caption_edges = (
                        media.get('edge_media_to_caption', {})
                        if isinstance(media.get('edge_media_to_caption'), dict)
                        else {}
                    )
                    edges = caption_edges.get('edges') if isinstance(caption_edges.get('edges'), list) else []
                    cap = ''
                    if edges:
                        node = edges[0].get('node') if isinstance(edges[0], dict) else None
                        if isinstance(node, dict):
                            cap = _preserve_caption(node.get('text') or '')

                    img = None
                    if isinstance(media.get('display_url'), str) and media.get('display_url'):
                        img = media.get('display_url')
                    elif isinstance(media.get('thumbnail_src'), str) and media.get('thumbnail_src'):
                        img = media.get('thumbnail_src')

                    return cap, img

                # Alternative shape: "items" list.
                items = data.get('items') if isinstance(data.get('items'), list) else []
                if items:
                    item0 = items[0] if isinstance(items[0], dict) else {}
                    cap = ''
                    caption_obj = item0.get('caption')
                    if isinstance(caption_obj, dict):
                        cap = _preserve_caption(caption_obj.get('text') or '')

                    img = None
                    # Try common image fields
                    for key in ['image_versions2', 'display_url', 'thumbnail_url', 'thumbnail_src']:
                        v = item0.get(key)
                        if isinstance(v, str) and v:
                            img = v
                            break
                        if isinstance(v, dict) and isinstance(v.get('candidates'), list) and v['candidates']:
                            cand0 = v['candidates'][0]
                            if isinstance(cand0, dict) and isinstance(cand0.get('url'), str):
                                img = cand0['url']
                                break
                    return cap, img

                return '', None
            except Exception:
                return '', None

        def _try_instagram_authenticated_json(target_url: str) -> tuple[str, str | None] | None:
            """Attempt authenticated JSON fetch using Instagram auth cookies.

            This is optional and only runs when public endpoints are blocked.
            """
            try:
                import json

                cookies, _has_raw = _get_instagram_auth_cookies()
                if not cookies.get('sessionid'):
                    return None

                try:
                    logger.info(
                        "Instagram auth cookie keys present: %s",
                        ",".join(sorted(cookies.keys())),
                    )
                except Exception:
                    pass

                from urllib.parse import urlsplit

                parts = urlsplit(target_url)
                path_parts = [p for p in (parts.path or '').split('/') if p]
                if len(path_parts) < 2:
                    return None

                kind = path_parts[0].lower()
                shortcode = path_parts[1]
                if kind not in {'reel', 'p', 'tv'}:
                    return None

                proxies, ua = _instagram_request_config()
                json_candidates = [
                    f"https://www.instagram.com/{kind}/{shortcode}/?__a=1&__d=dis",
                    f"https://www.instagram.com/{kind}/{shortcode}/?__a=1",
                    f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=dis",
                    f"https://www.instagram.com/p/{shortcode}/?__a=1",
                ]

                headers = {
                    "User-Agent": ua,
                    "Accept": "application/json, text/plain, */*",
                    "X-Requested-With": "XMLHttpRequest",
                    # Some deployments require these to avoid HTML/404 even with sessionid.
                    "X-IG-App-ID": "936619743392459",
                    "X-ASBD-ID": "129477",
                    "Referer": target_url,
                }

                if cookies.get('csrftoken'):
                    headers['X-CSRFToken'] = cookies['csrftoken']

                def _maybe_parse_instagram_json(resp: object) -> dict | None:
                    """Parse Instagram responses that may be JSON or `for (;;);{...}`."""
                    try:
                        text = (getattr(resp, 'text', '') or '').strip()
                        if not text:
                            return None

                        if text.startswith('for (;;);'):
                            text = text[len('for (;;);'):].lstrip()
                        # Some endpoints return JSON but with non-json content-type.
                        if text and text[0] in '{[':
                            data = json.loads(text)
                            return data if isinstance(data, dict) else None
                        return None
                    except Exception:
                        return None

                for json_url in json_candidates:
                    resp = requests.get(
                        json_url,
                        headers=headers,
                        cookies=cookies,
                        proxies=proxies,
                        timeout=10,
                    )

                    ct = (getattr(resp, 'headers', {}) or {}).get('Content-Type')
                    if getattr(resp, 'status_code', 0) >= 400:
                        logger.warning(
                            "Instagram auth JSON fetch failed (status=%s ct=%s url=%s)",
                            getattr(resp, 'status_code', None),
                            ct,
                            json_url,
                        )
                        continue

                    if ct and 'json' not in ct.lower():
                        # Instagram frequently returns application/x-javascript + `for (;;);{...}`
                        data = _maybe_parse_instagram_json(resp)
                        if not data:
                            snippet = (getattr(resp, 'text', '') or '')[:200]
                            logger.warning(
                                "Instagram auth JSON non-JSON response (ct=%s url=%s body=%s)",
                                ct,
                                json_url,
                                snippet,
                            )
                            continue
                    else:
                        try:
                            data = resp.json()
                        except Exception:
                            data = _maybe_parse_instagram_json(resp)
                            if not data:
                                snippet = (getattr(resp, 'text', '') or '')[:200]
                                logger.warning(
                                    "Instagram auth JSON parse failed (ct=%s url=%s body=%s)",
                                    ct,
                                    json_url,
                                    snippet,
                                )
                                continue

                    # If Instagram returns an error payload, treat as a miss.
                    if isinstance(data, dict) and data.get('error'):
                        logger.warning(
                            "Instagram auth JSON error payload (error=%s summary=%s url=%s)",
                            data.get('error'),
                            data.get('errorSummary'),
                            json_url,
                        )
                        continue

                    cap, img = _extract_caption_from_instagram_json(data)
                    if cap or img:
                        return cap, img

                return None
            except Exception as e:
                logger.warning("Instagram auth JSON exception (%s)", e)
                return None

        def _try_instagram_instaloader(target_url: str) -> tuple[str, str | None] | None:
            """Try Instaloader with session cookie as a last resort.

            Public endpoints can be blocked (JS shell). Instaloader often still works with a valid session.
            """
            sessionid = (os.environ.get('INSTAGRAM_SESSIONID') or '').strip()
            raw_cookies = (os.environ.get('INSTAGRAM_COOKIES') or '').strip()
            if not sessionid and not raw_cookies:
                return None

            try:
                import re
                import instaloader

                m = re.search(r"/(?:p|reel|tv)/([^/?#&]+)/?", target_url)
                if not m:
                    return None
                shortcode = m.group(1)

                proxies, _ua = _instagram_request_config()

                L = instaloader.Instaloader(quiet=True)
                try:
                    L.context.max_connection_attempts = 1
                except Exception:
                    pass
                try:
                    L.context.request_timeout = 10
                except Exception:
                    pass

                # Apply proxy to Instaloader session if configured.
                if proxies:
                    try:
                        L.context._session.proxies.update(proxies)
                    except Exception:
                        pass

                cookies: dict[str, str] = {}
                if raw_cookies:
                    for part in raw_cookies.split(';'):
                        part = part.strip()
                        if not part or '=' not in part:
                            continue
                        k, v = part.split('=', 1)
                        k = k.strip()
                        v = v.strip()
                        if k and v:
                            cookies[k] = v
                if sessionid and 'sessionid' not in cookies:
                    cookies['sessionid'] = sessionid
                csrftoken = (os.environ.get('INSTAGRAM_CSRFTOKEN') or '').strip()
                if csrftoken and 'csrftoken' not in cookies:
                    cookies['csrftoken'] = csrftoken
                ds_user_id = (os.environ.get('INSTAGRAM_DS_USER_ID') or '').strip()
                if ds_user_id and 'ds_user_id' not in cookies:
                    cookies['ds_user_id'] = ds_user_id

                try:
                    for k, v in cookies.items():
                        L.context._session.cookies.set(k, v, domain='.instagram.com')
                except Exception:
                    pass

                post = instaloader.Post.from_shortcode(L.context, shortcode)
                cap = (getattr(post, 'caption', '') or '').strip()
                img: str | None = None
                for attr in ['url', 'display_url', 'thumbnail_url', 'thumbnail_src']:
                    v = getattr(post, attr, None)
                    if isinstance(v, str) and v:
                        img = v
                        break
                    try:
                        s = str(v)
                        if s.startswith('http'):
                            img = s
                            break
                    except Exception:
                        pass

                if not cap and not img:
                    return None
                return cap, img
            except Exception as e:
                logger.warning("Instagram instaloader fallback failed (%s)", e)
                return None

        # Final fallback: if everything public is blocked, try optional authenticated JSON.
        if not caption:
            auth = _try_instagram_authenticated_json(url)
            if auth:
                auth_caption, auth_image = auth
                if auth_caption:
                    caption = auth_caption
                if auth_image and not image_url:
                    image_url = auth_image

        if not caption:
            il = _try_instagram_instaloader(url)
            if il:
                il_caption, il_image = il
                if il_caption:
                    caption = il_caption
                if il_image and not image_url:
                    image_url = il_image

        # Prefer the caption first line as title for IG (og:title is often "User on Instagram: \"...\"").
        if caption:
            cap_first = caption.splitlines()[0].strip()
            if cap_first and (not title or ' on instagram:' in title.lower()):
                title = clean_title(cap_first)[:200]

        # Parse ingredients/steps from caption if we don't have any.
        if caption and (not ingredients or not steps):
            cap_ings, cap_steps, cap_desc = _parse_caption_to_recipe(caption)
            if cap_ings and not ingredients:
                ingredients = cap_ings
            if cap_steps and not steps:
                steps = cap_steps
            if cap_desc and not description:
                description = cap_desc

        # As a fallback, keep the caption as description so the user gets *something*.
        if not description and caption:
            description = caption

        # Append original source line for traceability (requested UX).
        src_line = f"Originalreceptet är från {url}"
        if src_line not in (description or ''):
            description = f"{(description or '').strip()}\n\n{src_line}".strip()

        # If we still ended up with essentially nothing, log loudly for production debugging.
        if not title or (not ingredients and not steps and (description or '').strip() == src_line):
            logger.error(
                "Instagram import empty (url=%s did_try_oembed=%s oembed_ok=%s title=%r og_title=%r og_desc_len=%s caption_len=%s)",
                url,
                did_try_oembed,
                oembed_ok,
                title,
                og_title_text,
                len(og_desc_text or ''),
                len(caption or ''),
            )
    
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
        # On Landleys, the #recept-content element is often just an anchor/title marker.
        # The actual recipe card (ingredients/steps) may appear AFTER it in the DOM.
        anchor = soup.select_one("#recept-content")
        scope = anchor if anchor is not None else soup

        # Prefer the actual recipe title from "Recept på X" if present inside the recipe section.
        # (Article title can be "Så enkelt är det att göra ...", which is not the recipe name.)
        def normalize_landley_title(raw: str) -> str:
            s = clean_title(raw)
            if not s:
                return s
            if s.strip().lower() == "pulled pork":
                return "Pulled Pork"
            # Default: keep as-is (avoid aggressive titlecasing of Swedish), but ensure first letter is uppercase.
            return s[:1].upper() + s[1:] if s else s

        if scope is not None:
            # Avoid regex over the whole scope text (which may collapse newlines) – find the actual heading node.
            for h in scope.find_all(["h1", "h2", "h3", "h4"]):
                t = clean_text(h.get_text(" ", strip=True))
                m = re.search(r"\bRecept\s+p[åa]\s+(.+)$", t, re.IGNORECASE)
                if m:
                    possible = normalize_landley_title(m.group(1))
                    if possible:
                        title = possible
                        break

        # If we didn't find it inside the anchor container, fall back to scanning headings globally.
        if title and title.lower().startswith("så enkelt är det att göra "):
            # Article title style -> strip the prefix.
            rest = title[len("så enkelt är det att göra "):].strip()
            if rest and rest == rest.lower():
                rest = rest.title()
            title = rest or title

        if not title or title.lower().startswith("så enkelt är det att göra "):
            for h in soup.find_all(["h1", "h2", "h3", "h4"]):
                t = clean_text(h.get_text(" ", strip=True))
                m = re.search(r"\bRecept\s+p[åa]\s+(.+)$", t, re.IGNORECASE)
                if m:
                    possible = normalize_landley_title(m.group(1))
                    if possible:
                        title = possible
                        break

        # First-class: Landleys uses microdata ingredients with <br> separators (no <ul>/<li>).
        #
        # NOTE: On the live site we have observed duplicate `itemprop` attributes in the HTML which
        # means the parsed DOM may only keep the LAST one (often "ingredients"). Therefore we match
        # both `recipeIngredient` and `ingredients`.
        if not ingredients:
            micro_els = soup.select('[itemprop="recipeIngredient"], [itemprop="ingredients"]')
            micro_lines: list[str] = []
            for el in micro_els:
                raw = el.get_text("\n", strip=True)
                for ln in raw.splitlines():
                    t = clean_text(ln)
                    if t:
                        micro_lines.append(t)
            # Deduplicate while preserving order
            if micro_lines:
                seen = set()
                deduped: list[str] = []
                for x in micro_lines:
                    if x in seen:
                        continue
                    seen.add(x)
                    deduped.append(x)
                ingredients = deduped

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

        def looks_like_nav(lines: list[str]) -> bool:
            if not lines:
                return False
            joined = " ".join(lines).lower()
            if any(b in joined for b in bad_snippets):
                return True

            # Ingredient lists usually contain units (dl, msk, g...) in multiple lines.
            unit_hits = sum(1 for x in lines if unit_re.search(x or ""))
            digit_hits = sum(1 for x in lines if re.search(r"\d", x or ""))

            # A nav/menu list might contain "2.0" etc but no real units.
            if unit_hits == 0:
                return True

            # If we have units but almost no digits, it's suspicious too.
            if digit_hits == 0:
                return True

            return False

        def choose_best_ingredient_list(root) -> list[str]:
            candidates: list[list[str]] = []
            for ul in root.find_all("ul"):
                items = [clean_text(li.get_text(" ", strip=True)) for li in ul.find_all("li")]
                items = [x for x in items if x]
                if len(items) < 3:
                    continue
                # Heuristic: ingredient lists usually contain digits/units in many lines.
                # Reject obvious nav lists.
                if looks_like_nav(items):
                    continue

                digit_score = sum(1 for x in items if re.search(r"\d", x))
                unit_score = sum(1 for x in items if unit_re.search(x or ""))
                if digit_score == 0 or unit_score == 0:
                    continue
                score = digit_score + unit_score
                candidates.append(items)

            if not candidates:
                return []

            # Choose the list with highest "digit-line" count.
            candidates.sort(
                key=lambda lst: (
                    sum(1 for x in lst if unit_re.search(x or "")),
                    sum(1 for x in lst if re.search(r"\d", x or "")),
                    len(lst),
                ),
                reverse=True,
            )
            best = candidates[0]
            return best

        def extract_quantity_lines(root) -> list[str]:
            """
            Landleys sometimes uses checkbox-style markup, not <li>. Extract ingredient-like lines by pattern.
            """
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

                # 1) Try inside anchor element itself (some pages include the full card inside it)
                extracted = choose_best_ingredient_list(root)
                if not extracted:
                    extracted = extract_quantity_lines(root)

                # 2) If anchor is only a marker, scan forward in the DOM for the actual ingredients.
                # Landleys often renders ingredients as checkbox/label/div markup (not <ul>/<li>),
                # and the anchor itself only contains a heading.
                if not extracted and anchor is not None:
                    # Ingredient lines typically start with a quantity and unit. Comments/nav do not.
                    qty_unit_re = re.compile(
                        r"^\s*\d+(?:[.,]\d+)?\s*(?:"
                        r"kg|g|mg|l|dl|cl|ml|msk|tsk|krm|st|styck|stycken"
                        r")\b",
                        re.IGNORECASE,
                    )
                    comment_snippets = [
                        "kommentar",
                        "kommentarer",
                        "svara",
                        "lämna en kommentar",
                        "reply",
                    ]
                    # First try: scan for ingredient-like lines in following elements (checkbox-style markup).
                    lines: list[str] = []
                    # Stop scanning once we reach the comments heading/area.
                    for el in anchor.find_all_next(["h2", "h3", "h4", "label", "li", "p", "span"], limit=3500):
                        t = clean_text(el.get_text(" ", strip=True))
                        if not t:
                            continue
                        tl = t.lower()
                        if el.name in ("h2", "h3", "h4") and ("kommentar" in tl or "kommentarer" in tl):
                            break
                        if any(b in tl for b in bad_snippets):
                            continue
                        if any(s in tl for s in comment_snippets):
                            continue
                        if qty_unit_re.search(t) and unit_re.search(t):
                            # Avoid temperatures/times; keep units like "msk" etc.
                            if "°" in t or "grader" in tl:
                                continue
                            if re.search(r"\b(min|minuter|tim|timmar)\b", tl):
                                continue
                            if len(t) <= 140:
                                lines.append(t)
                        if len(lines) >= 25:
                            # Enough ingredients; stop early.
                            break

                    # If that didn't work, try UL-based candidates (some pages still use <ul>).
                    if not lines:
                        candidates: list[list[str]] = []
                        for ul in anchor.find_all_next("ul", limit=80):
                            items = [clean_text(li.get_text(" ", strip=True)) for li in ul.find_all("li")]
                            items = [x for x in items if x]
                            if len(items) < 3:
                                continue
                            if looks_like_nav(items):
                                continue
                            joined = " ".join(items).lower()
                            if any(s in joined for s in comment_snippets):
                                continue

                            qty_hits = sum(1 for x in items if qty_unit_re.search(x or ""))
                            unit_hits = sum(1 for x in items if unit_re.search(x or ""))
                            if unit_hits == 0 or qty_hits < 2:
                                continue
                            candidates.append(items)

                        if candidates:
                            candidates.sort(
                                key=lambda lst: (
                                    sum(1 for x in lst if qty_unit_re.search(x or "")),
                                    sum(1 for x in lst if unit_re.search(x or "")),
                                    len(lst),
                                ),
                                reverse=True,
                            )
                            lines = candidates[0]

                    if lines:
                        # Deduplicate while preserving order
                        seen = set()
                        deduped: list[str] = []
                        for x in lines:
                            if x in seen:
                                continue
                            seen.add(x)
                            deduped.append(x)
                        extracted = deduped

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


def import_recipe_from_url(url: str, source_text: str | None = None) -> ImportedRecipeData:
    url = _normalize_url(url)
    if not url:
        raise ValueError('Missing url')

    # Instagram share links often include tracking query params like ?igsh=...
    # These can cause different (more restricted) responses and also confuse oEmbed.
    if 'instagram.com' in url.lower():
        try:
            from urllib.parse import urlsplit, urlunsplit

            parts = urlsplit(url)
            url = urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
        except Exception:
            pass

    final_url, content = fetch_html(url)
    return import_recipe_from_html(final_url, content, source_text=source_text)
