from __future__ import annotations

from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from .api_views import (
    AppleLoginView,
    CookbookViewSet,
    RecipeViewSet,
    ShoppingListItemViewSet,
    ShoppingListViewSet,
    WeeklyMenuItemViewSet,
    WeeklyMenuViewSet,
    WeeklyPlanViewSet,
)

router = DefaultRouter()
router.register(r'recipes', RecipeViewSet, basename='recipe')
router.register(r'cookbooks', CookbookViewSet, basename='cookbook')
router.register(r'shopping-lists', ShoppingListViewSet, basename='shoppinglist')
router.register(r'shopping-list-items', ShoppingListItemViewSet, basename='shoppinglistitem')
router.register(r'weekly-plan', WeeklyPlanViewSet, basename='weeklyplan')
router.register(r'weekly-menus', WeeklyMenuViewSet, basename='weeklymenu')
router.register(r'weekly-menu-items', WeeklyMenuItemViewSet, basename='weeklymenuitem')

urlpatterns = [
    path('auth/token/', obtain_auth_token, name='api-token'),
    path('auth/apple/', AppleLoginView.as_view(), name='api-auth-apple'),
    path('', include(router.urls)),
]
