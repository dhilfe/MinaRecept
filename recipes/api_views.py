from __future__ import annotations

import json
import logging
import time
from functools import lru_cache

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from jose import jwt
from rest_framework import permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

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

logger = logging.getLogger(__name__)

class AppleLoginView(APIView):
    """
    Exchanges an Apple Sign-In ID Token for a Django Auth Token.
    Creates a new user if one doesn't exist.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        id_token = request.data.get('id_token')
        if not id_token:
            return Response({'detail': 'Missing id_token.'}, status=status.HTTP_400_BAD_REQUEST)

        # Optional name fields provided by client on first login
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')

        try:
            # 1. Fetch Apple's public keys
            apple_public_keys = self.get_apple_keys()
            
            # 2. Decode header to find the Key ID (kid)
            header = jwt.get_unverified_header(id_token)
            kid = header.get('kid')
            
            # 3. Find the correct key
            key = next(k for k in apple_public_keys if k['kid'] == kid)
            
            # 4. Verify the token
            # Audience should be the Bundle ID (client_id)
            # We support multiple clients (e.g. App and Extension) so we might need to check against a list,
            # but usually it's the main App Bundle ID.
            # For now, we accept the audience if it matches our expected bundle ID.
            
            decoded = jwt.decode(
                id_token,
                key,
                algorithms=['RS256'],
                audience=settings.SOCIALACCOUNT_PROVIDERS['apple']['APP']['client_id'],
                options={'verify_exp': True} # Check expiration
            )
            
            # 5. Extract user info
            apple_sub = decoded.get('sub') # Unique Apple User ID
            email = decoded.get('email', '')
            
            if not apple_sub:
                return Response({'detail': 'Invalid token: missing sub.'}, status=status.HTTP_400_BAD_REQUEST)

            # 6. Find or Create User
            user = self.get_or_create_user(apple_sub, email, first_name, last_name)
            
            # 7. Generate/Get Token
            token, _ = Token.objects.get_or_create(user=user)
            
            return Response({
                'token': token.key,
                'user_id': user.pk,
                'email': user.email,
                'username': user.username
            })

        except StopIteration:
            return Response({'detail': 'Invalid token: matching key not found.'}, status=status.HTTP_400_BAD_REQUEST)
        except jwt.ExpiredSignatureError:
            return Response({'detail': 'Token has expired.'}, status=status.HTTP_400_BAD_REQUEST)
        except jwt.JWTClaimsError as e:
            return Response({'detail': f'Token claims invalid: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Apple Login failed")
            return Response({'detail': f'Login failed: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

    @lru_cache(maxsize=1)
    def get_apple_keys(self):
        """Fetch and cache Apple's public keys."""
        # Cache for a while (LRU cache handles in-memory caching)
        # In a real production app, you might want to handle cache expiration more explicitly,
        # but keys rotate infrequently.
        url = "https://appleid.apple.com/auth/keys"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()['keys']

    def get_or_create_user(self, apple_sub, email, first_name, last_name):
        # Strategy:
        # 1. Look for user by 'username' = apple_sub (Most reliable)
        # 2. Look for user by 'email' (if provided)
        # 3. Create new user
        
        # Check by sub (username)
        user = User.objects.filter(username=apple_sub).first()
        if user:
            return user
            
        # Check by email
        if email:
            user = User.objects.filter(email__iexact=email).first()
            if user:
                # Link this user to the apple_sub? 
                # Ideally we shouldn't change the username of an existing user as it might break things,
                # but we can rely on the email match.
                # For future consistency, we might want to store the apple_sub in a separate profile or SocialAccount,
                # but for this MVP, logging them in is sufficient.
                return user
        
        # Create new
        # Use apple_sub as username to ensure uniqueness and stability
        user = User.objects.create_user(
            username=apple_sub,
            email=email,
            password=None # Unusable password
        )
        
        if first_name: user.first_name = first_name
        if last_name: user.last_name = last_name
        user.save()
        
        return user


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

    @action(
        detail=False,
        methods=["post"],
        url_path="import-image",
        parser_classes=[MultiPartParser, FormParser],
    )
    def import_from_image(self, request):
        """
        Import a recipe from a shared image (OCR).

        Used by iOS Share Extension when an app shares only a UIImage (no URL).
        Expects multipart/form-data with:
          - image: the image file (jpeg/png)
          - dish_type: optional recipe category id
        """
        dish_type = (request.data.get("dish_type") or "").strip()
        # Backwards compatibility: older clients may send "everyday".
        if dish_type == "everyday":
            dish_type = "lunch_dinner"
        if dish_type:
            valid_types = {choice[0] for choice in Recipe.TYPE_CHOICES}
            if dish_type not in valid_types:
                return Response({"detail": "Invalid dish_type."}, status=status.HTTP_400_BAD_REQUEST)

        image_file = request.FILES.get("image") or request.FILES.get("recipe_image")
        if not image_file:
            return Response({"detail": "Missing image."}, status=status.HTTP_400_BAD_REQUEST)

        provided_title = (request.data.get("title") or "").strip()

        def safe_int(value, default: int) -> int:
            """
            Best-effort int conversion for OCR output.
            Handles numbers, numeric strings, and strings like "30 min" / "PT30M" (extracts first integer).
            """
            try:
                if value is None:
                    return default
                if isinstance(value, bool):
                    return default
                if isinstance(value, int):
                    return value
                if isinstance(value, float):
                    return int(value)
                s = str(value).strip()
                if not s:
                    return default
                import re
                m = re.search(r"(\d+)", s)
                if not m:
                    return default
                return int(m.group(1))
            except Exception:
                return default

        data: dict = {}
        try:
            from .ocr_service import ImageRecipeParser

            parser = ImageRecipeParser()
            parsed = parser.parse_image(image_file)
            if isinstance(parsed, dict):
                data = parsed
        except Exception:
            # Never fail hard here: Share Extension expects a 201 for good UX.
            logger.exception("Image import OCR failed (will create placeholder recipe)")
            data = {}

        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()
        ingredients = (data.get("ingredients") or "").strip()
        steps = (data.get("steps") or "").strip()
        cooking_time = safe_int(data.get("cooking_time"), default=0)
        servings = safe_int(data.get("servings"), default=4)

        # If OCR fell back to the mock parser (no API key), prefer a user-provided title.
        if provided_title and (not title or title.lower().startswith("mockat recept")):
            title = provided_title

        # If OCR couldn't extract anything meaningful, still create a placeholder recipe.
        # This avoids "Kunde inte spara" from the Share Extension and lets the user edit later.
        if not title and not ingredients and not steps:
            title = provided_title or "Importerad bild"
            description = (
                "Kunde inte tolka recept från bilden automatiskt. "
                "Kontrollera att bilden är tydlig, eller fyll i receptet manuellt."
            )

        recipe = Recipe.objects.create(
            user=request.user,
            title=title or "Importerad bild",
            description=description,
            ingredients=ingredients,
            steps=steps,
            cooking_time=max(1, cooking_time) if cooking_time else 30,
            servings=max(1, servings) if servings else 4,
            dish_type=dish_type or Recipe._meta.get_field("dish_type").default,
        )

        # Best-effort: save the uploaded image on the recipe as well.
        try:
            image_file.seek(0)
        except Exception:
            pass
        try:
            recipe.image.save(getattr(image_file, "name", "share.jpg"), image_file, save=True)
        except Exception:
            # Non-fatal: OCR text is still saved, and user can add an image later.
            logger.exception("Image import: failed to save uploaded image to recipe (non-fatal)")

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
