from __future__ import annotations

import json
import re

from rest_framework import serializers

from .models import (
    Cookbook,
    Recipe,
    ShoppingList,
    ShoppingListItem,
    WeeklyPlan,
    WeeklyMenu,
    WeeklyMenuItem,
)

from .services import format_amount, parse_legacy_ingredient_line


class RecipeSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    def validate_ingredients(self, value: str) -> str:
        """Normalize ingredients to the canonical JSON-string format.

        iOS expects the backend to return `ingredients` as a JSON-encoded list of
        objects: [{"amount": "...", "unit": "...", "name": "..."}].

        We still accept legacy multiline text and convert it.
        """
        return _normalize_ingredients_to_json_string(value)

    def update(self, instance: Recipe, validated_data: dict) -> Recipe:
        old_servings = getattr(instance, 'servings', None) or 0
        new_servings = validated_data.get('servings', old_servings) or 0

        # If servings changes and the client did not explicitly provide ingredients,
        # rescale existing ingredient amounts to keep the recipe consistent.
        if (
            'servings' in validated_data
            and old_servings > 0
            and new_servings > 0
            and new_servings != old_servings
            and 'ingredients' not in validated_data
        ):
            base = _normalize_ingredients_to_json_string(instance.ingredients)
            validated_data['ingredients'] = _scale_ingredients_json_string(
                base,
                old_servings=old_servings,
                new_servings=new_servings,
            )

        return super().update(instance, validated_data)

    class Meta:
        model = Recipe
        fields = [
            'id',
            'user',
            'title',
            'description',
            'ingredients',
            'steps',
            'cooking_time',
            'difficulty',
            'dish_type',
            'tags',
            'servings',
            'image',
            'image_url',
            'is_favorite',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_image_url(self, obj: Recipe):
        request = self.context.get('request')
        if not obj.image:
            return obj.image_url
        url = obj.image.url
        if request is None:
            return url
        return request.build_absolute_uri(url)


def _normalize_ingredients_to_json_string(raw: str | None) -> str:
    text = (raw or '').strip()
    if not text:
        return '[]'

    # Already JSON?
    try:
        decoded = json.loads(text)
        if isinstance(decoded, list):
            return text
    except Exception:
        pass

    # Legacy multiline text -> structured list.
    out: list[dict[str, str]] = []
    for line in text.splitlines():
        parsed = parse_legacy_ingredient_line(line)
        if not parsed:
            continue
        name, amount, unit = parsed
        out.append(
            {
                'name': (name or '').strip(),
                'amount': (amount or '').strip(),
                'unit': (unit or '').strip(),
            }
        )

    return json.dumps(out, ensure_ascii=False)


def _scale_ingredients_json_string(raw_json: str, *, old_servings: int, new_servings: int) -> str:
    if old_servings <= 0 or new_servings <= 0 or old_servings == new_servings:
        return raw_json

    factor = float(new_servings) / float(old_servings)
    if abs(factor - 1.0) < 1e-12:
        return raw_json

    try:
        decoded = json.loads(raw_json)
    except Exception:
        return raw_json

    if not isinstance(decoded, list):
        return raw_json

    for ing in decoded:
        if not isinstance(ing, dict):
            continue
        amount = str(ing.get('amount') or '').strip()
        if not amount:
            continue
        ing['amount'] = _scale_amount_string(amount, factor)

    return json.dumps(decoded, ensure_ascii=False)


_DASH_RE = re.compile(r'[–—]')
_RANGE_RE = re.compile(r'^\s*(?P<a>[^-]+?)\s*-\s*(?P<b>[^-]+?)\s*$')
_MIXED_FRACTION_RE = re.compile(r'^\s*(?P<int>\d+)\s+(?P<num>\d+)\s*/\s*(?P<den>\d+)\s*$')
_FRACTION_RE = re.compile(r'^\s*(?P<num>\d+)\s*/\s*(?P<den>\d+)\s*$')
_NUMBER_RE = re.compile(r'^\s*(?P<num>\d+(?:[\.,]\d+)?)\s*$')


def _parse_amount_token(token: str) -> float | None:
    t = (token or '').strip()
    if not t:
        return None

    m = _MIXED_FRACTION_RE.match(t)
    if m:
        try:
            whole = int(m.group('int'))
            num = int(m.group('num'))
            den = int(m.group('den'))
            if den == 0:
                return None
            return float(whole) + (float(num) / float(den))
        except Exception:
            return None

    m = _FRACTION_RE.match(t)
    if m:
        try:
            num = int(m.group('num'))
            den = int(m.group('den'))
            if den == 0:
                return None
            return float(num) / float(den)
        except Exception:
            return None

    m = _NUMBER_RE.match(t)
    if m:
        try:
            return float(m.group('num').replace(',', '.'))
        except Exception:
            return None

    return None


def _scale_amount_string(amount: str, factor: float) -> str:
    if not amount or abs(factor - 1.0) < 1e-12:
        return amount

    normalized = _DASH_RE.sub('-', amount).strip()

    # Range: "1-2" / "1 - 2"
    m = _RANGE_RE.match(normalized)
    if m:
        a = _parse_amount_token(m.group('a'))
        b = _parse_amount_token(m.group('b'))
        if a is None or b is None:
            return amount
        return f"{format_amount(a * factor)}-{format_amount(b * factor)}"

    # Single value
    val = _parse_amount_token(normalized)
    if val is None:
        return amount

    return format_amount(val * factor)


class CookbookSerializer(serializers.ModelSerializer):
    recipe_count = serializers.IntegerField(source='recipes.count', read_only=True)
    preview_image_urls = serializers.SerializerMethodField()

    def get_preview_image_urls(self, obj: Cookbook) -> list[str]:
        request = self.context.get('request')

        qs = obj.recipes.all().order_by('-updated_at', '-created_at')
        urls: list[str] = []
        for recipe in qs[:3]:
            if recipe.image:
                url = recipe.image.url
                if request is not None:
                    url = request.build_absolute_uri(url)
                urls.append(url)
            elif recipe.image_url:
                urls.append(recipe.image_url)

        return urls

    def validate_name(self, value: str) -> str:
        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError('This field may not be blank.')

        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            qs = Cookbook.objects.filter(user=user, name=name)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError('A cookbook with this name already exists.')

        return name

    class Meta:
        model = Cookbook
        fields = ['id', 'user', 'name', 'created_at', 'updated_at', 'recipe_count', 'preview_image_urls']
        read_only_fields = ['user', 'created_at', 'updated_at', 'recipe_count', 'preview_image_urls']


class ShoppingListSerializer(serializers.ModelSerializer):
    item_count = serializers.IntegerField(source='items.count', read_only=True)

    class Meta:
        model = ShoppingList
        fields = ['id', 'user', 'name', 'is_recurring', 'is_main', 'created_at', 'updated_at', 'item_count']
        read_only_fields = ['user', 'created_at', 'updated_at']


class ShoppingListItemSerializer(serializers.ModelSerializer):
    recipe_title = serializers.CharField(source='recipe.title', read_only=True)

    class Meta:
        model = ShoppingListItem
        fields = [
            'id',
            'user',
            'shopping_list',
            'recipe',
            'recipe_title',
            'name',
            'amount',
            'unit',
            'checked',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def validate_shopping_list(self, value):
        request = self.context.get('request')
        if request is None or value is None:
            return value
        if value.user_id != request.user.id:
            raise serializers.ValidationError('Invalid shopping_list.')
        return value

    def validate_recipe(self, value):
        request = self.context.get('request')
        if request is None or value is None:
            return value
        if value.user_id != request.user.id:
            raise serializers.ValidationError('Invalid recipe.')
        return value


class WeeklyPlanSerializer(serializers.ModelSerializer):
    recipe_title = serializers.CharField(source='recipe.title', read_only=True)

    class Meta:
        model = WeeklyPlan
        fields = ['id', 'user', 'day', 'recipe', 'recipe_title']
        read_only_fields = ['user']

    def validate_recipe(self, value):
        request = self.context.get('request')
        if request is None:
            return value
        if value.user_id != request.user.id:
            raise serializers.ValidationError('Invalid recipe.')
        return value


class WeeklyMenuItemSerializer(serializers.ModelSerializer):
    recipe_title = serializers.CharField(source='recipe.title', read_only=True)

    class Meta:
        model = WeeklyMenuItem
        fields = ['id', 'menu', 'day', 'recipe', 'recipe_title']

    def validate_menu(self, value):
        request = self.context.get('request')
        if request is None:
            return value
        if value.user_id != request.user.id:
            raise serializers.ValidationError('Invalid menu.')
        return value

    def validate_recipe(self, value):
        request = self.context.get('request')
        if request is None:
            return value
        if value.user_id != request.user.id:
            raise serializers.ValidationError('Invalid recipe.')
        return value


class WeeklyMenuSerializer(serializers.ModelSerializer):
    items = WeeklyMenuItemSerializer(many=True, read_only=True)

    class Meta:
        model = WeeklyMenu
        fields = ['id', 'user', 'name', 'week_number', 'year', 'servings', 'created_at', 'items']
        read_only_fields = ['user', 'created_at']
