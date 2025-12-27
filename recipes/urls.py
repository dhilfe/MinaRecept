from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.RecipeListView.as_view(), name='recipe_list'),
    path('login/', auth_views.LoginView.as_view(template_name='recipes/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    path('recipe/<int:pk>/', views.RecipeDetailView.as_view(), name='recipe_detail'),
    path('recipe/<int:pk>/cook/', views.RecipeCookView.as_view(), name='recipe_cook'),
    path('recipe/new/', views.RecipeCreateView.as_view(), name='recipe_create'),
    path('recipe/import/', views.recipe_import, name='recipe_import'),
    path('recipe/import-image/', views.recipe_import_image, name='recipe_import_image'),
    path('recipe/bookmarklet/', views.bookmarklet_view, name='bookmarklet_info'),
    path('recipe/<int:pk>/edit/', views.RecipeUpdateView.as_view(), name='recipe_update'),
    path('recipe/<int:pk>/delete/', views.RecipeDeleteView.as_view(), name='recipe_delete'),

    # Multi shopping lists
    path('shopping-lists/', views.shopping_lists_view, name='shopping_lists'),
    # Backwards-compatible alias (nav/history)
    path('shopping-list/', views.shopping_lists_view, name='shopping_list'),
    path('shopping-lists/<int:list_id>/', views.shopping_list_detail_view, name='shopping_list_detail'),

    # Choose list (or create) before adding ingredients
    path('recipe/<int:pk>/shopping-list/add/', views.choose_shopping_list_for_recipe, name='choose_shopping_list_for_recipe'),
    
    path('weekly-plan/', views.weekly_plan_view, name='weekly_plan'),
    path('weekly-plan/save/', views.save_weekly_menu, name='save_weekly_menu'),
    path('weekly-plan/update/', views.update_menu_day, name='update_menu_day'),
    path('weekly-plan/remove/<int:pk>/', views.remove_from_menu, name='remove_from_menu'),
    path('weekly-plan/random/', views.generate_random_menu, name='generate_random_menu'),
    path('weekly-plan/add-to-shopping-list/', views.add_weekly_menu_to_shopping_list, name='add_weekly_menu_to_shopping_list'),
    path('weekly-plan/clear/', views.clear_menu, name='clear_menu'),
]
