from __future__ import annotations

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


class RecipeSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

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


class CookbookSerializer(serializers.ModelSerializer):
    recipe_count = serializers.IntegerField(source='recipes.count', read_only=True)

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
        fields = ['id', 'user', 'name', 'created_at', 'updated_at', 'recipe_count']
        read_only_fields = ['user', 'created_at', 'updated_at', 'recipe_count']


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
