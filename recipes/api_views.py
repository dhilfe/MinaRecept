from __future__ import annotations

from rest_framework import permissions, viewsets

from .models import Recipe, ShoppingList, ShoppingListItem, WeeklyMenu, WeeklyMenuItem, WeeklyPlan
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
