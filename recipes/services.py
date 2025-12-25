import json
import re
from .models import ShoppingListItem, ShoppingListRecipeSource

def to_float(value: str):
    try:
        return float(str(value).strip().replace(',', '.'))
    except Exception:
        return None

def format_amount(value: float) -> str:
    try:
        if value is None:
            return ''
        rounded = round(value)
        if abs(value - rounded) < 1e-9:
            return str(int(rounded))
        return ('{:g}'.format(value)).replace('.', ',')
    except Exception:
        return str(value)

def parse_legacy_ingredient_line(line: str):
    text = (line or '').strip()
    if not text:
        return None

    # Strip common bullet/list prefixes
    text = re.sub(r'^[\s\-•*]+', '', text)
    text = re.sub(r'^\s*\d+[\).]\s+', '', text)

    # Strip common prefixes like "ca", "cirka", "ungefär"
    text = re.sub(r'^\s*(ca\.?|cirka|ungefär)\s+', '', text, flags=re.IGNORECASE)

    # Ignore section headers like "Fyllning:" / "Sås:" in imported ingredient lists
    if re.match(r'^[^:]{1,80}:\s*$', text):
        return None

    # Examples we want to handle:
    # - "2 dl mjöl" -> ("mjöl", "2", "dl")
    # - "1-2 st ägg" -> ("ägg", "1-2", "st")
    # - "1 1/2 dl mjölk" -> ("mjölk", "1 1/2", "dl")
    # - "salt" -> ("salt", "", "")
    amount_re = r'(?:\d+(?:[\.,]\d+)?|\d+/\d+)(?:\s+\d+/\d+)?(?:\s*[–-]\s*\d+(?:[\.,]\d+)?)?'
    m = re.match(rf'^\s*(?P<amount>{amount_re})\s*(?P<unit>[A-Za-zÅÄÖåäö\.]+)?\s+(?P<name>.+?)\s*$', text)
    if m:
        amount = (m.group('amount') or '').strip()
        unit = (m.group('unit') or '').strip().strip('.')
        name = (m.group('name') or '').strip()
        return name, amount, unit

    return text, '', ''

def upsert_shopping_list_item(user, shopping_list, name, amount, unit, recipe=None):
    """
    Adds or updates a shopping list item.
    Returns (item, created) tuple.
    """
    name = name.strip()
    amount = amount.strip()
    unit = unit.strip()
    
    if not name:
        return None, False

    # Try to find existing item
    existing = ShoppingListItem.objects.filter(
        user=user,
        shopping_list=shopping_list,
        checked=False,
        name__iexact=name,
        unit__iexact=unit,
    ).first() if unit else ShoppingListItem.objects.filter(
        user=user,
        shopping_list=shopping_list,
        checked=False,
        name__iexact=name,
        unit='',
    ).first()

    if existing:
        # Merge logic
        if amount:
            a1 = to_float(existing.amount)
            a2 = to_float(amount)
            if a1 is not None and a2 is not None:
                existing.amount = format_amount(a1 + a2)
            elif a1 is None and a2 is not None and not (existing.amount or '').strip():
                existing.amount = amount
            else:
                # Fallback concatenation if we can't do math
                if existing.amount:
                     existing.amount = f"{existing.amount} + {amount}"
                else:
                     existing.amount = amount
        else:
            # No new amount, treat as +1 if existing has numeric amount
            a1 = to_float(existing.amount)
            if a1 is not None:
                existing.amount = format_amount(a1 + 1)
            elif not (existing.amount or '').strip():
                existing.amount = '1'
            else:
                existing.amount = f"{existing.amount} + 1"
        
        if recipe:
            existing.recipe = recipe
        
        existing.save(update_fields=['amount', 'recipe', 'updated_at'] if recipe else ['amount', 'updated_at'])
        return existing, False
    else:
        # Create new
        item = ShoppingListItem.objects.create(
            user=user,
            shopping_list=shopping_list,
            recipe=recipe,
            name=name,
            amount=amount,
            unit=unit,
            checked=False,
        )
        return item, True

def add_ingredients_to_list(user, recipe, shopping_list):
    """
    Adds ingredients from a recipe to a shopping list.
    Returns a dict with 'added' (int), 'merged' (int), and 'already_exists' (bool).
    """
    if ShoppingListRecipeSource.objects.filter(user=user, shopping_list=shopping_list, recipe=recipe).exists():
        return {'added': 0, 'merged': 0, 'already_exists': True}

    added = 0
    merged = 0

    # Try JSON ingredients first
    ingredients = None
    try:
        parsed = json.loads(recipe.ingredients)
        if isinstance(parsed, list):
            ingredients = parsed
    except Exception:
        ingredients = None

    if ingredients is not None:
        for ing in ingredients:
            if not isinstance(ing, dict):
                continue
            name = str(ing.get('name') or '').strip()
            amount = str(ing.get('amount') or '').strip()
            unit = str(ing.get('unit') or '').strip()
            if name.endswith(':') and not amount and not unit:
                continue
            if not name:
                continue

            _, created = upsert_shopping_list_item(user, shopping_list, name, amount, unit, recipe)
            if created:
                added += 1
            else:
                merged += 1
    else:
        # Legacy text lines
        for line in recipe.ingredients.splitlines():
            parsed = parse_legacy_ingredient_line(line)
            if not parsed:
                continue
            name, amount, unit = parsed
            _, created = upsert_shopping_list_item(user, shopping_list, name, amount, unit, recipe)
            if created:
                added += 1
            else:
                merged += 1

    if added or merged:
        ShoppingListRecipeSource.objects.create(user=user, shopping_list=shopping_list, recipe=recipe)
    
    return {'added': added, 'merged': merged, 'already_exists': False}
