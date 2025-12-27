from __future__ import annotations

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Recipe, ShoppingList, ShoppingListItem, ShoppingListRecipeSource, WeeklyMenu, WeeklyMenuItem, WeeklyPlan
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

        dish_type = (request.data.get('dish_type') or '').strip()
        # Backwards compatibility: older clients may send "everyday".
        if dish_type == 'everyday':
            dish_type = 'lunch_dinner'
        if dish_type:
            valid_types = {choice[0] for choice in Recipe.TYPE_CHOICES}
            if dish_type not in valid_types:
                return Response({'detail': 'Invalid dish_type.'}, status=status.HTTP_400_BAD_REQUEST)

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
            dish_type=dish_type or Recipe._meta.get_field('dish_type').default,
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
    queryset = ShoppingList.objects.all().order_by('-is_main', '-updated_at', '-created_at')
    serializer_class = ShoppingListSerializer

    @action(detail=True, methods=['post'])
    def clear(self, request, pk=None):
        shopping_list = self.get_object()
        ShoppingListItem.objects.filter(shopping_list=shopping_list).delete()
        ShoppingListRecipeSource.objects.filter(shopping_list=shopping_list).delete()
        return Response({'detail': 'List cleared.'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='uncheck-all')
    def uncheck_all(self, request, pk=None):
        shopping_list = self.get_object()
        shopping_list.items.update(checked=False)
        return Response({'detail': 'All items unchecked.'}, status=status.HTTP_200_OK)


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

    @action(detail=False, methods=['post'])
    def randomize(self, request):
        # Clear existing plan
        WeeklyPlan.objects.filter(user=request.user).delete()
        
        # Get random recipes (default: lunch/dinner)
        queryset = Recipe.objects.filter(user=request.user, dish_type='lunch_dinner')
        count = queryset.count()
        
        if count == 0:
               return Response({'detail': 'Inga lunch-/middagsrecept hittades. Kategorisera dina recept som "Lunch/Middag".'}, status=status.HTTP_400_BAD_REQUEST)
             
        # We want 7 recipes, or as many as we have
        limit = min(count, 7)
        recipes = list(queryset.order_by('?')[:limit])
        
        days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        
        plan_items = []
        for i, day in enumerate(days):
            # Cycle through recipes if we have fewer than 7
            recipe = recipes[i % len(recipes)]
            plan_items.append(WeeklyPlan(user=request.user, day=day, recipe=recipe))
            
        WeeklyPlan.objects.bulk_create(plan_items)
        
        # Return the new plan
        new_plan = WeeklyPlan.objects.filter(user=request.user)
        serializer = self.get_serializer(new_plan, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='save-as-menu')
    def save_as_menu(self, request):
        plan_items = WeeklyPlan.objects.filter(user=request.user)
        if not plan_items.exists():
            return Response({'detail': 'Din veckoplan är tom.'}, status=status.HTTP_400_BAD_REQUEST)

        name = (request.data.get('name') or '').strip()
        if not name:
            from django.utils import timezone
            today = timezone.now().date()
            date_str = today.strftime('%Y-%m-%d')
            # Find existing menus with this date prefix to determine sequence
            count = WeeklyMenu.objects.filter(user=request.user, name__startswith=date_str).count()
            name = f"{date_str}-{count + 1}"

        servings = request.data.get('servings')
        if servings:
            try:
                servings = int(servings)
            except ValueError:
                servings = 4 # Default
        else:
            servings = 4

        menu = WeeklyMenu.objects.create(user=request.user, name=name, servings=servings)
        
        menu_items = []
        for item in plan_items:
            menu_items.append(WeeklyMenuItem(menu=menu, day=item.day, recipe=item.recipe))
        
        WeeklyMenuItem.objects.bulk_create(menu_items)
        
        return Response({'detail': 'Veckoplan sparad som meny.', 'id': menu.id, 'name': menu.name}, status=status.HTTP_201_CREATED)


class WeeklyMenuViewSet(OwnedModelViewSet):
    queryset = WeeklyMenu.objects.all().order_by('-created_at')
    serializer_class = WeeklyMenuSerializer

    @action(detail=True, methods=['get'], url_path='shopping-list')
    def shopping_list(self, request, pk=None):
        menu = self.get_object()
        items = menu.items.select_related('recipe').all()
        
        aggregated = {}
        pantry_notes = set()
        
        from .services import clean_ingredient_name, parse_legacy_ingredient_line, to_float, format_amount
        from .categorization import categorize_ingredient
        import json
        import re

        def normalize_unit(raw: str):
            u = (raw or '').strip().strip('.').lower()
            if not u:
                return "", 1.0

            # Normalize common Swedish/English variants.
            aliases = {
                "gram": "g",
                "gr": "g",
                "kilogram": "kg",
                "kilo": "kg",
                "liter": "l",
                "litr": "l",
                "st": "st",
                "styck": "st",
                "stycken": "st",
                "pcs": "st",
                "pc": "st",
                "piece": "st",
                "pieces": "st",
            }
            u = aliases.get(u, u)

            # Convert metric scale units to a canonical base.
            weight = {"mg": ("g", 0.001), "g": ("g", 1.0), "kg": ("g", 1000.0)}
            volume = {"ml": ("ml", 1.0), "cl": ("ml", 10.0), "dl": ("ml", 100.0), "l": ("ml", 1000.0)}
            if u in weight:
                return weight[u]
            if u in volume:
                return volume[u]

            # Keep other units as-is (e.g. tsk/msk) but normalized.
            return u, 1.0

        def is_salt_or_peppar(clean_name: str) -> bool:
            s = (clean_name or '').strip().lower()
            if not s:
                return False

            # Match word-boundary forms and compound words like "havssalt" / "svartpeppar".
            if re.search(r'\bsalt\b', s) or any(tok.endswith('salt') for tok in s.split()):
                return True
            if re.search(r'\bpeppar\b', s) or any(tok.endswith('peppar') for tok in s.split()):
                return True
            return False

        def add_salt_peppar_notes(clean_name: str) -> None:
            s = (clean_name or '').strip().lower()
            if not s:
                return
            if re.search(r'\bsalt\b', s) or any(tok.endswith('salt') for tok in s.split()):
                pantry_notes.add('Salt')
            if re.search(r'\bpeppar\b', s) or any(tok.endswith('peppar') for tok in s.split()):
                pantry_notes.add('Peppar')

        def is_butter(clean_name: str) -> bool:
            return (clean_name or '').strip().lower() == 'smör'
        
        for item in items:
            recipe = item.recipe
            
            # Calculate scaling factor
            scaling_factor = 1.0
            if menu.servings and recipe.servings:
                scaling_factor = menu.servings / recipe.servings

            ingredients = []
            
            # Parse ingredients
            try:
                parsed = json.loads(recipe.ingredients)
                if isinstance(parsed, list):
                    for ing in parsed:
                        if isinstance(ing, dict):
                            name = str(ing.get('name') or '').strip()
                            amount = str(ing.get('amount') or '').strip()
                            unit = str(ing.get('unit') or '').strip()
                            ingredients.append((name, amount, unit))
            except:
                pass
                
            if not ingredients:
                for line in recipe.ingredients.splitlines():
                    parsed = parse_legacy_ingredient_line(line)
                    if parsed:
                        ingredients.append(parsed)
            
            for name, amount, unit in ingredients:
                clean_name = clean_ingredient_name(name)
                if not clean_name:
                    continue

                # Salt/pepper should ALWAYS be pantry notes (deduplicated), even if a quantity is provided.
                if is_salt_or_peppar(clean_name):
                    add_salt_peppar_notes(clean_name)
                    continue
                
                # Apply scaling
                amount_val = to_float(amount)
                if amount_val is not None:
                    amount_val *= scaling_factor
                unit_norm, unit_factor = normalize_unit(unit)

                if amount_val is not None and unit_factor != 1.0:
                    amount_val = amount_val * unit_factor

                if amount_val is not None:
                    amount = format_amount(amount_val)

                unit = unit_norm

                # Butter: only include as an ingredient if it is a bigger amount (>= 50g).
                # Otherwise treat it as a pantry note (typically "smör att steka i").
                if is_butter(clean_name):
                    if amount_val is not None and unit == 'g' and amount_val >= 50:
                        # keep as ingredient
                        pass
                    else:
                        pantry_notes.add('Smör (att steka i)')
                        continue

                key = f"{clean_name.lower()}|{unit.lower()}" if unit else clean_name.lower()
                
                if key not in aggregated:
                    aggregated[key] = {
                        'name': clean_name,
                        'amount': amount,
                        'unit': unit,
                        'category': categorize_ingredient(clean_name)
                    }
                else:
                    # Merge
                    existing = aggregated[key]

                    a1 = to_float(existing['amount'])
                    a2 = to_float(amount)
                    if a1 is not None and a2 is not None:
                        existing['amount'] = format_amount(a1 + a2)
                    elif amount:
                        # Fallback concatenation if we can't do math
                        if existing['amount']:
                            existing['amount'] = f"{existing['amount']} + {amount}"
                        else:
                            existing['amount'] = amount

        # Group by category
        by_category = {}
        
        for key, data in aggregated.items():
            cat = data['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(data)
            
        category_order = ["Frukt & Grönt", "Mejeri & Ost", "Kött, Fisk & Fågel", "Bröd & Bageri", "Skafferi", "Frys", "Övrigt"]
        
        sorted_result = []
        for cat in category_order:
            if cat in by_category:
                items = sorted(by_category[cat], key=lambda x: x['name'])
                sorted_result.append({'category': cat, 'items': items})

        if pantry_notes:
            sorted_result.append({
                'category': 'Kryddor att ha hemma',
                'items': [{'name': n, 'amount': '', 'unit': '', 'category': 'Övrigt'} for n in sorted(pantry_notes)]
            })
                
        return Response(sorted_result)



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
