from __future__ import annotations

import json
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def parse_json(value):
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return None


def _normalize_for_match(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _clean_ingredient_name(value: str) -> str:
    s = _normalize_for_match(value)
    if not s:
        return ""
    # Drop parenthetical notes and trailing punctuation.
    s = re.sub(r"\([^)]*\)", "", s)
    # Keep the part before commas/semicolons (common for "salt, efter smak").
    s = re.split(r"[,;]", s, maxsplit=1)[0]
    s = s.strip(" .,:;\t\n\r")
    return _normalize_for_match(s)


def _letter_tokens(value: str) -> list[str]:
    # Unicode letters only (no digits/underscore). Works well for Swedish.
    return re.findall(r"[^\W\d_]+", value, flags=re.UNICODE)


@register.filter
def ingredient_names(value):
    """Return a list of ingredient names from either JSON or legacy text."""
    parsed = parse_json(value)
    names: list[str] = []

    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                name = _clean_ingredient_name(str(item.get("name", "")))
                if name:
                    names.append(name)
    else:
        # Legacy: attempt to strip a leading amount/unit and keep the remainder.
        for raw_line in str(value or "").splitlines():
            line = _normalize_for_match(raw_line)
            if not line:
                continue
            # Skip header-like lines (e.g., "Sås:")
            if line.endswith(":"):
                continue
            # Remove leading amount (incl. fractions) + unit-ish tokens.
            line = re.sub(
                r"^\s*\d+(?:[\.,]\d+)?(?:\s+\d+/\d+|\s*\d+/\d+)?\s*", "", line, flags=re.IGNORECASE
            )
            line = re.sub(r"^(?:st|dl|cl|l|ml|g|kg|msk|tsk|krm)\b\s*", "", line, flags=re.IGNORECASE)
            line = _clean_ingredient_name(line)
            if line:
                names.append(line)

    # Deduplicate while preserving order, and ignore very short/common tokens.
    seen: set[str] = set()
    result: list[str] = []
    for name in names:
        key = name.lower()
        if len(key) < 3:
            continue
        if key in seen:
            continue
        seen.add(key)
        result.append(name)
    return result


@register.filter
def underline_ingredients(text: str, names):
    """Underline ingredient mentions in instruction text.

    Uses a simple heuristic: match ingredient name as a prefix and allow extra
    letters (e.g. "tomat" matches "tomaterna", "tomatsåsen").
    """
    if not text:
        return ""

    if not names:
        return escape(text)

    name_list = [n for n in names if isinstance(n, str) and n.strip()]
    if not name_list:
        return escape(text)

    # Match longer names first to avoid partial matches.
    name_list.sort(key=lambda s: len(s), reverse=True)

    # Allow plural/definite suffix in Swedish etc (unicode letters) + hyphen.
    suffix = r"(?:[^\W\d_]|-)*"

    parts: list[str] = []
    for raw_name in name_list:
        n = _clean_ingredient_name(raw_name)
        if not n or len(n) < 3:
            continue

        tokens = _letter_tokens(n)
        if not tokens:
            continue

        # Allow optional whitespace/hyphen (or none) between words: "röd lök" == "rödlök" == "röd-lök".
        escaped_tokens = [re.escape(t) for t in tokens]
        joined = r"\s*-?\s*".join(escaped_tokens)
        parts.append(rf"{joined}{suffix}")

    if not parts:
        return escape(text)

    pattern = re.compile(r"(" + "|".join(parts) + r")", flags=re.IGNORECASE | re.UNICODE)
    escaped = escape(text)
    underlined = pattern.sub(r'<span class="text-decoration-underline">\1</span>', escaped)
    return mark_safe(underlined)
