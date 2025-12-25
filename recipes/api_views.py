from __future__ import annotations

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Recipe, ShoppingList, ShoppingListItem, WeeklyMenu, WeeklyMenuItem, WeeklyPlan
from .importing import import_recipe_from_url
from .services import add_ingredients_to_list
from .serializers import (
    RecipeSerializer,
    ShoppingListItemSerializer,
    ShoppingListSerializer,
    WeeklyMenuItemSerializer,
    WeeklyMenuSerializer,
    WeeklyPlanSerializer,
)


class OwnedModelViewSet(viewsets.ModelViewSet):
    """Base viewset for models with a `user` FK."""

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RecipeViewSet(OwnedModelViewSet):
    queryset = Recipe.objects.all().order_by('-updated_at', '-created_at')
    serializer_class = RecipeSerializer

    @action(detail=False, methods=['post'], url_path='import')
    def import_from_url(self, request):
        url = (request.data.get('url') or '').strip()
        if not url:
            return Response({'detail': 'Missing url.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            imported = import_recipe_from_url(url)
        except Exception as e:
            return Response({'detail': f'Import failed: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        recipe = Recipe.objects.create(
            user=request.user,
            title=imported.title,
            description=imported.description,
            ingredients='\n'.join(imported.ingredients),
            steps='\n'.join(imported.steps),
            cooking_time=imported.cooking_time,
            servings=imported.servings,
            image_url=imported.image_url,
        )

        serializer = self.get_serializer(recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='add-to-shopping-list')
    def add_to_shopping_list(self, request, pk=None):
        recipe = self.get_object()
        list_id = request.data.get('shopping_list_id')
        
        if not list_id:
            # Default to main list
            shopping_list = ShoppingList.objects.filter(user=request.user, is_main=True).first()
            if not shopping_list:
                shopping_list = ShoppingList.objects.create(user=request.user, name="Inköpslista", is_main=True)
        else:
            try:
                shopping_list = ShoppingList.objects.get(id=list_id, user=request.user)
            except ShoppingList.DoesNotExist:
                return Response({'detail': 'Shopping list not found.'}, status=status.HTTP_404_NOT_FOUND)

        result = add_ingredients_to_list(request.user, recipe, shopping_list)
        
        if result['already_exists']:
            return Response({'detail': 'Ingredients already added to this list.', 'result': result}, status=status.HTTP_200_OK)
            
        return Response({'detail': 'Ingredients added.', 'result': result}, status=status.HTTP_200_OK)


class ShoppingListViewSet(OwnedModelViewSet):
    queryset = ShoppingList.objects.all().order_by('-updated_at', '-created_at')
    serializer_class = ShoppingListSerializer


class ShoppingListItemViewSet(OwnedModelViewSet):
    queryset = ShoppingListItem.objects.all().order_by('checked', 'name', '-updated_at', '-created_at')
    serializer_class = ShoppingListItemSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        shopping_list_id = self.request.query_params.get('shopping_list')
        if shopping_list_id:
            queryset = queryset.filter(shopping_list_id=shopping_list_id)
        return queryset


class WeeklyPlanViewSet(OwnedModelViewSet):
    queryset = WeeklyPlan.objects.all()
    serializer_class = WeeklyPlanSerializer


class WeeklyMenuViewSet(OwnedModelViewSet):
    queryset = WeeklyMenu.objects.all().order_by('-created_at')
    serializer_class = WeeklyMenuSerializer


class WeeklyMenuItemViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = WeeklyMenuItem.objects.all()
    serializer_class = WeeklyMenuItemSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(menu__user=self.request.user)
        menu_id = self.request.query_params.get('menu')
        if menu_id:
            queryset = queryset.filter(menu_id=menu_id)
        return queryset
