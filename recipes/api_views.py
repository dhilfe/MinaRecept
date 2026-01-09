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

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by search query (title, ingredients, tags)
        search = self.request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(ingredients__icontains=search) |
                Q(tags__icontains=search)
            )
        
        # Filter by specific tags
        tags = self.request.query_params.get('tags', '').strip()
        if tags:
            # Support comma-separated tags: "snabb,enkel"
            tag_list = [t.strip().lower() for t in tags.split(',') if t.strip()]
            for tag in tag_list:
                queryset = queryset.filter(tags__icontains=tag)
        
        return queryset

    @action(detail=False, methods=['post'], url_path='import')
    def import_from_url(self, request):
        url = (request.data.get('url') or '').strip()
        if not url:
            return Response({'detail': 'Missing url.'}, status=status.HTTP_400_BAD_REQUEST)

        source_text = (request.data.get('source_text') or '').strip()

        if 'instagram.com' in url.lower():
            has_markers = any(k in source_text.lower() for k in ['ingredien', 'gör så', 'gor sa', 'instructions'])
            logger.info(
                "IG import request: url=%s source_text_len=%s has_markers=%s",
                url,
                len(source_text),
                has_markers,
            )

        dish_type = (request.data.get('dish_type') or '').strip()
        # Backwards compatibility: older clients may send "everyday".
        if dish_type == 'everyday':
            dish_type = 'lunch_dinner'
        if dish_type:
            valid_types = {choice[0] for choice in Recipe.TYPE_CHOICES}
            if dish_type not in valid_types:
                return Response({'detail': 'Invalid dish_type.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            imported = import_recipe_from_url(url, source_text=source_text or None)
        except Exception as e:
            return Response({'detail': f'Import failed: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        def normalize_tags(raw: str) -> str:
            parts = [p.strip() for p in (raw or "").split(",")]
            parts = [p for p in parts if p]
            seen: set[str] = set()
            out: list[str] = []
            for p in parts:
                key = p.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(p)
            return ", ".join(out)

        requested_tags = normalize_tags((request.data.get("tags") or "").strip())

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
            tags=requested_tags,
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

        # Note: Recipe.title is max_length=200, but we keep the raw value for possible parsing/salvage.
        provided_title_raw = (request.data.get("title") or "")
        provided_title = provided_title_raw.strip()

        source_url = (request.data.get("source_url") or "").strip()
        source_text = (request.data.get("source_text") or "").strip()

        # Performance: for Instagram shares we often already have the full caption (source_text).
        # In that case OCR is low-signal (thumbnail image) and can add seconds of latency.
        is_instagram = "instagram.com" in (source_url or "").lower()

        def normalize_tags(raw: str) -> str:
            parts = [p.strip() for p in (raw or "").split(",")]
            parts = [p for p in parts if p]
            seen: set[str] = set()
            out: list[str] = []
            for p in parts:
                key = p.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(p)
            return ", ".join(out)

        requested_tags = normalize_tags((request.data.get("tags") or "").strip())

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
        if not (is_instagram and source_text):
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

        caption_ingredients_duplicate_steps = False
        caption_ingredients_salvaged = False

        def parse_caption_to_recipe(text: str) -> tuple[str, str, str]:
            """
            Best-effort parse for Instagram captions.
            Returns (ingredients, steps, description_extra).
            """
            import re
            import html

            # Instagram captions may contain HTML entities (e.g. "p&#xe5;", "&#x1f31f;").
            raw = html.unescape((text or "")).replace("\r\n", "\n").replace("\r", "\n")
            # Some IG/OG sources may include literal "\n" sequences instead of actual newlines.
            raw = raw.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")

            # Remove obvious URLs
            raw = re.sub(r"https?://\S+", "", raw)
            lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
            if not lines:
                return "", "", ""

            def looks_like_step_line(line: str) -> bool:
                s = (line or "").strip()
                if not s:
                    return False
                if s.startswith("(") and s.endswith(")"):
                    return False
                # Captions often prefix steps with emojis or arrows (e.g. "👉 Stek ...").
                # Strip non-letter prefix before verb matching.
                s = re.sub(r"^[^A-Za-zÅÄÖåäö]+", "", s).strip()
                # Common Swedish cooking verbs at the beginning of a step.
                # This is more reliable than length heuristics (ingredients can be long too).
                if re.match(
                    r"(?i)^(stek\w*|tillsätt\w*|strö\w*|servera\w*|lägg\w*|häll\w*|ringla\w*|toppa\w*|bland\w*|visp\w*|rör\w*|kok\w*|låt\w*|hack\w*|skär\w*|sätt\w*|form\w*|smak\w*|bryn\w*)\b",
                    s,
                ) is not None:
                    return True

                # Also treat long instruction-like sentences as steps even if they don't start with a verb.
                # This captures patterns like "I en skål blandar du ...".
                if len(s) >= 60 and (
                    "." in s
                    or "!" in s
                    or "?" in s
                    or re.search(r"(?i)\b(min|minuter|grader|°c)\b", s)
                ):
                    if re.search(
                        r"(?i)\b(stek\w*|tillsätt\w*|strö\w*|servera\w*|lägg\w*|häll\w*|ringla\w*|toppa\w*|bland\w*|visp\w*|rör\w*|kok\w*|låt\w*|hack\w*|skär\w*|sätt\w*|form\w*|smak\w*|bryn\w*)\b",
                        s,
                    ):
                        return True

                return False

            def is_numbered_step_line(line: str) -> bool:
                """Detect step lines that start with numbering.

                We accept:
                - "1." / "1)" styles
                - "1 <verb> ..." styles (common in captions)

                We deliberately avoid matching ingredient quantities like "1 dl" or ranges like "1-2 tsk".
                """
                s = (line or "").strip()
                if not s:
                    return False

                # Strong signal: explicit punctuation after the number.
                if re.match(r"^\s*\d+\s*[.)]\s*\S+", s):
                    return True

                # Also accept bare "1 <...>" but only if what follows looks like a step (starts with a verb).
                m = re.match(r"^\s*(\d+)\s+(\S.+)$", s)
                if not m:
                    return False
                rest = m.group(2).strip()
                rest = re.sub(r"^[^A-Za-zÅÄÖåäö]+", "", rest).strip()
                return looks_like_step_line(rest)

            def is_heading(line: str) -> bool:
                l = line.strip()
                if l.endswith(":"):
                    return True
                # common headings (allow extra punctuation/emojis, e.g. "Ingredienser👇")
                # Strip parenthetical info like "Gör så här (tar typ 5 minuter)"
                low = re.sub(r"\(.*?\)", "", l).lower().rstrip(":").strip()
                if "ingredien" in low or low == "ingredients" or low == "recept":
                    return True
                # Common ingredient heading variant in Swedish captions.
                if "du behöver" in low or "du behover" in low:
                    return True
                # Accept common variations: "Gör så här", "Gör såhär", "För så här" (typo), "Så här gör du"
                if any(pattern in low for pattern in ["gör så", "gör sa", "görsåhär", "görsahar", "för så här", "så här gör"]):
                    return True
                if "instruktion" in low or "tillag" in low or low == "instructions":
                    return True
                return False

            def normalize_heading(line: str) -> str:
                # Strip parenthetical info and normalize
                s = re.sub(r"\(.*?\)", "", line).strip().rstrip(":").strip()
                return s

            # Identify sections
            ing_start = None
            step_start = None
            numbered_step_idx = None
            first_subsection_idx = None  # Track first colon-ending line (like "Biffar:" or "Sås:")
            
            for i, ln in enumerate(lines):
                # Strip parentheses for comparison
                low = re.sub(r"\(.*?\)", "", ln).lower().rstrip(":").strip()
                
                # Track first subsection heading (ends with colon, not a major heading)
                if first_subsection_idx is None and ln.strip().endswith(":"):
                    if not any(
                        kw in low
                        for kw in [
                            "ingredien",
                            "recept",
                            "du behöver",
                            "du behover",
                            "gör",
                            "gor",
                            "instruktion",
                            "tillag",
                        ]
                    ):
                        first_subsection_idx = i
                
                # Accept "Ingredienser", "Ingredients", or "Recept" as ingredient marker
                if ing_start is None and (
                    "ingredien" in low
                    or low == "ingredients"
                    or low == "recept"
                    or "du behöver" in low
                    or "du behover" in low
                ):
                    ing_start = i + 1
                    continue
                # Accept variations: "Gör så här", "För så här", "Gör såhär", "Så här gör du"
                if step_start is None and any(pattern in low for pattern in ["gör så", "gör sa", "görsåhär", "görsahar", "för så här", "så här gör"]):
                    step_start = i + 1
                    continue
                if step_start is None and ("instruktion" in low or low == "instructions" or "tillag" in low):
                    step_start = i + 1
                    continue
                # NOTE: don't treat "1-2 tsk ..." as a step (common ingredient amount).
                # Accept numbered steps including "1."/"1)" and "1 <verb>".
                if numbered_step_idx is None and is_numbered_step_line(ln):
                    numbered_step_idx = i
            
            # Fallback: if no explicit ingredient marker but we have subsections (e.g., "Biffar:", "Sås:"),
            # treat first subsection as start of ingredient section.
            if ing_start is None and first_subsection_idx is not None:
                ing_start = first_subsection_idx

            # If no explicit step marker exists but we do have numbered steps, use those.
            if step_start is None and numbered_step_idx is not None:
                step_start = numbered_step_idx

            def collect_until_next_heading(start_idx: int | None, is_ingredient_section: bool = False) -> list[str]:
                """Collect lines until next heading. 
                
                If is_ingredient_section=True and we're after a 'Recept' heading, stop when we hit
                long sentences (likely steps).
                """
                if start_idx is None:
                    return []
                out: list[str] = []
                for i, ln in enumerate(lines[start_idx:], start=start_idx):
                    if is_heading(ln):
                        break
                    if ln.lstrip().startswith("#"):
                        # Ignore hashtags.
                        continue
                    # Ignore parenthetical notes/tips at line level too.
                    if ln.strip().startswith("(") and ln.strip().endswith(")"):
                        continue
                    
                    s = ln.strip()
                    # If this is ingredient section after "Recept:", stop when we hit step-like lines.
                    if is_ingredient_section and looks_like_step_line(s):
                        break
                    
                    # strip bullet markers
                    s = re.sub(r"^[-•*]+\\s*", "", s).strip()
                    if s:
                        out.append(s)
                return out

            def normalize_numbered_steps(raw_steps: list[str]) -> list[str]:
                """Merge continuation lines into the preceding numbered step and strip leading numbers.

                The iOS UI numbers each step itself, so returning "1. ..." would duplicate numbering.
                """
                out: list[str] = []
                current: str = ""

                for ln in raw_steps:
                    s = ln.strip()
                    if not s:
                        continue
                    if s.startswith("#"):
                        continue
                    # Ignore lines that are parenthetical notes/tips (common at end of captions).
                    if s.startswith("(") and s.endswith(")"):
                        continue

                    m = re.match(r"^\s*\d+\s*[.)]\s*(\S.+)$", s)
                    if m:
                        if current:
                            out.append(current.strip())
                        current = m.group(1).strip()
                        continue

                    m2 = re.match(r"^\s*\d+\s+(\S.+)$", s)
                    if m2 and looks_like_step_line(m2.group(1)):
                        if current:
                            out.append(current.strip())
                        current = m2.group(1).strip()
                        continue

                    # Continuation line (belongs to the previous step)
                    if current:
                        current = (current + " " + s).strip()
                    else:
                        # If we somehow start with a continuation, treat as its own step.
                        current = s

                if current:
                    out.append(current.strip())

                return out

            # Check if this is a "Recept:" heading (ingredient marker variation)
            is_recept_heading = ing_start is not None and ing_start > 0
            if is_recept_heading:
                prev_line = lines[ing_start - 1].lower().strip().rstrip(":")
                is_recept_heading = prev_line == "recept"

            ing_lines = collect_until_next_heading(ing_start, is_ingredient_section=is_recept_heading)
            step_lines = collect_until_next_heading(step_start)

            # Filter out parenthetical notes from step_lines before processing.
            step_lines = [ln for ln in step_lines if not (ln.strip().startswith("(") and ln.strip().endswith(")"))]

            # If steps look like numbered steps, merge continuation lines and strip numbering.
            if step_lines and any(is_numbered_step_line(ln) for ln in step_lines):
                step_lines = normalize_numbered_steps(step_lines)

            # Common Reel caption format:
            # Intro text -> "Dressing:" block -> "Sallad:" block -> numbered steps.
            # If we have numbered steps but no explicit ingredients marker, treat the content
            # before the first numbered step as ingredients (preserving subsection headings ending with ":").
            if not ing_lines and numbered_step_idx is not None and ing_start is None:
                # Find first subsection heading before steps.
                ing_block_start = None
                for i, ln in enumerate(lines[:numbered_step_idx]):
                    if ln.strip().endswith(":"):
                        ing_block_start = i
                        break
                if ing_block_start is None:
                    ing_block_start = 1 if numbered_step_idx > 1 else 0

                desc_extra = ""
                if ing_block_start > 1:
                    desc_extra = "\n".join(lines[1:ing_block_start]).strip()

                ing_out: list[str] = []
                for ln in lines[ing_block_start:numbered_step_idx]:
                    if ln.strip().endswith(":"):
                        h = normalize_heading(ln)
                        if h:
                            ing_out.append(h + ":")
                        continue
                    s = re.sub(r"^[-•*]+\s*", "", ln).strip()
                    if s:
                        ing_out.append(s)

                # Prefer whatever we already collected for steps (it starts at the numbered lines).
                step_out = [s for s in step_lines if s and not s.strip().startswith("#")]
                if step_out and any(is_numbered_step_line(ln) for ln in step_out):
                    step_out = normalize_numbered_steps(step_out)
                if not step_out:
                    raw_step_lines: list[str] = []
                    for ln in lines[numbered_step_idx:]:
                        s = ln.strip()
                        if not s or s.startswith("#"):
                            continue
                        raw_step_lines.append(s)
                    if any(is_numbered_step_line(ln) for ln in raw_step_lines):
                        step_out = normalize_numbered_steps(raw_step_lines)
                    else:
                        step_out = raw_step_lines

                if ing_out or step_out or desc_extra:
                    return "\n".join(ing_out).strip(), "\n".join(step_out).strip(), desc_extra

            # If we truly have no markers at all, keep caption as description only.
            # (Important: don't early-return just because the initial collectors returned empty;
            # add_headings() may still recover ingredients from subsection headings like "Biffar:".)
            if ing_start is None and step_start is None and numbered_step_idx is None:
                return "", "", raw.strip()

            # Preserve headings like "Dressing:" by converting to a plain heading line.
            # We'll add them if we see lines ending with ":" in the relevant span.
            def add_headings(start_idx: int | None, collected: list[str]) -> list[str]:
                """Process lines starting from start_idx, preserving subsection headings.

                Stop when hitting long sentences (likely steps) if we're in ingredient section.
                """
                if start_idx is None:
                    return collected
                out: list[str] = []
                for ln in lines[start_idx:]:
                    if is_heading(ln) and (
                        "ingredien" in ln.lower()
                        or "du behöver" in ln.lower()
                        or "du behover" in ln.lower()
                        or "gör" in ln.lower()
                        or "instruktion" in ln.lower()
                        or "recept" in ln.lower()
                    ):
                        # Stop at next major section
                        break
                    if ln.endswith(":") and normalize_heading(ln):
                        out.append(normalize_heading(ln) + ":")
                        continue
                    if is_heading(ln):
                        break

                    # If we hit numbered steps (common when the caption has no explicit "Gör så här" heading),
                    # stop collecting ingredients so steps don't end up duplicated under Ingredienser.
                    if is_numbered_step_line(ln):
                        break

                    s = ln.strip()
                    # Stop if we hit a step-like line (likely a step, not ingredient)
                    if looks_like_step_line(s):
                        break

                    s = re.sub(r"^[-•*]+\\s*", "", s).strip()
                    if s:
                        out.append(s)
                # fallback to original collected if we got nothing
                return out or collected

            ing_lines = add_headings(ing_start, ing_lines)
            # Don't re-process step_lines with add_headings as we've already filtered/normalized them.
            # step_lines = add_headings(step_start, step_lines)

            # After add_headings processes ingredients and stops at long sentences,
            # collect those long sentences as steps if we don't have explicit steps yet.
            if ing_lines and not step_lines and ing_start is not None:
                # Find where add_headings stopped (first long sentence after ing_start)
                step_start_idx = None
                for i, ln in enumerate(lines[ing_start:], start=ing_start):
                    if is_heading(ln) and any(kw in ln.lower() for kw in ["ingredien", "gör", "instruktion", "recept"]):
                        break
                    # Skip subsection headings
                    if ln.strip().endswith(":"):
                        continue
                    s = ln.strip()
                    if looks_like_step_line(s):
                        step_start_idx = i
                        break

                if step_start_idx is not None:
                    potential_steps = []
                    for ln in lines[step_start_idx:]:
                        s = ln.strip()
                        if not s or s.startswith("#"):
                            continue
                        if s.startswith("(") and s.endswith(")"):
                            continue
                        potential_steps.append(s)

                    if potential_steps:
                        step_lines = potential_steps

            # If we still couldn't extract any structure, keep caption as description only.
            if not ing_lines and not step_lines:
                return "", "", raw.strip()

            # If we found steps but no explicit ingredient section, try to extract obvious
            # ingredient lines before the step section (common in Reel captions).
            if not ing_lines and step_lines:
                def looks_like_ingredient_line(line: str) -> bool:
                    s = (line or "").strip().lower()
                    if not s:
                        return False
                    if s.endswith(":") and len(s) <= 30:
                        return True
                    if re.match(r"^\s*\d+(?:[\.,]\d+)?\s*(?:g|gr|kg|dl|cl|l|ml|msk|tsk|krm|st|pkt|förp|burk)\b", s):
                        return True
                    if re.match(r"^\s*\d+\s*(?:st|stycken)\b", s):
                        return True
                    if re.match(r"^\s*\d+\s*(?:-\s*\d+)?\s*(?:tsk|msk)\b", s):
                        return True
                    if ("&" in s or " och " in s) and re.search(r"(?i)\b(salt|peppar|vitpeppar|svartpeppar|socker)\b", s):
                        # Avoid capturing instruction-y sentences.
                        if looks_like_step_line(s):
                            return False
                        return True
                    return False

                search_span = lines
                if step_start is not None and step_start > 0:
                    search_span = lines[:step_start]

                extracted: list[str] = []
                for ln in search_span:
                    if not ln or ln.lstrip().startswith("#"):
                        continue
                    if is_heading(ln):
                        continue
                    s = re.sub(r"^[-•*]+\s*", "", (ln or "").strip()).strip()
                    if not s:
                        continue
                    if is_numbered_step_line(s) or looks_like_step_line(s):
                        continue
                    if looks_like_ingredient_line(s):
                        extracted.append(s)

                if extracted:
                    ing_lines = extracted

            return "\n".join(ing_lines).strip(), "\n".join(step_lines).strip(), ""

        def salvage_from_blob(blob: str):
            """
            Best-effort salvage when OCR or the client dumps most text into the title field.
            Tries to split into title/ingredients/steps using Swedish section markers.
            """
            import re

            raw = (blob or "").strip()
            if not raw:
                return "", "", "", ""

            normalized = raw.replace("\r\n", "\n")
            lines = [ln.strip() for ln in normalized.split("\n") if ln.strip()]
            if not lines:
                return "", "", "", ""

            # Helper: find marker line index (case-insensitive, diacritics-insensitive-ish)
            def find_line_index(patterns):
                for i, ln in enumerate(lines):
                    s = ln.lower()
                    for p in patterns:
                        if p in s:
                            return i
                return None

            idx_ing = find_line_index(["ingredienser", "ingredients", "du behöver", "du behover"])
            idx_steps = find_line_index(["gör så här", "gor sa har", "instruktioner", "tillagning", "metod", "steg"])

            # Title = first line up to 200 chars (later capped).
            salv_title = lines[0]

            salv_desc = ""
            salv_ing = ""
            salv_steps = ""

            # If we have explicit sections, use them.
            if idx_ing is not None:
                ing_start = idx_ing + 1
                ing_end = idx_steps if (idx_steps is not None and idx_steps > ing_start) else len(lines)
                salv_ing = "\n".join(lines[ing_start:ing_end]).strip()

            if idx_steps is not None:
                steps_start = idx_steps + 1
                salv_steps = "\n".join(lines[steps_start:]).strip()

            # If still missing, try heuristic step lines like "1." / "1)"
            if not salv_steps:
                step_lines = [ln for ln in lines if re.match(r"^\s*\d+\s*[.)]\s*\S+", ln)]
                if step_lines:
                    salv_steps = "\n".join(step_lines).strip()

            # If we found a lot of content but no sections, keep the remainder as description.
            if not salv_ing and not salv_steps and len(lines) > 1:
                salv_desc = "\n".join(lines[1:]).strip()

            return salv_title, salv_desc, salv_ing, salv_steps

        # If OCR failed to populate ingredients/steps but dumped content into title/description,
        # try to salvage. Prefer the OCR title blob, otherwise fall back to raw provided title.
        if not ingredients and not steps:
            blob = title if (len(title) > 120 or "\n" in title) else ""
            if not blob and provided_title_raw:
                blob = provided_title_raw
            if blob:
                s_title, s_desc, s_ing, s_steps = salvage_from_blob(blob)
                # If title is clearly a blob (multiline or contains section markers), replace it with the salvaged title.
                if s_title:
                    lower_blob = blob.lower()
                    should_replace_title = ("\n" in blob) or ("ingredien" in lower_blob) or ("gör" in lower_blob) or ("gor" in lower_blob)
                    if not title or should_replace_title:
                        title = s_title
                if s_desc and not description:
                    description = s_desc
                if s_ing and not ingredients:
                    ingredients = s_ing
                if s_steps and not steps:
                    steps = s_steps

        # Instagram caption fallback:
        # If source_url is Instagram and we have source_text, prefer it over OCR output.
        # This avoids the common case where OCR returns mock/placeholder ingredients/steps
        # (e.g. when OPENAI_API_KEY is missing) and blocks caption parsing.
        if source_text and is_instagram:
            parsed_ing, parsed_steps, desc_extra = parse_caption_to_recipe(source_text)

            # For Instagram thumbnail imports, OCR output is often low-signal (it's not a recipe screenshot).
            # Prefer a caption-derived title unless the client explicitly provided one.
            if not provided_title:
                import re
                import html

                def guess_instagram_title(caption: str) -> str:
                    t = html.unescape((caption or "")).replace("\r\n", "\n").strip()
                    if not t:
                        return ""

                    # Strip instagram og:description prefix: "username Month DD, YYYY: \"...\""
                    t = re.sub(r"^\S+\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}:\s*\"?", "", t).strip()
                    t = t.strip('"')
                    t = re.sub(r"\"\.?$", "", t).strip()

                    # Remove URLs to avoid polluting the title.
                    t = re.sub(r"https?://\S+", "", t).strip()

                    # First try: extract after "recept ... på (en/ett) ..." up to punctuation.
                    m = re.search(r"(?i)\brecept\b[^\n.!?]*?\bpå\b\s*(?:en|ett)?\s*([^\n.!?\"]+)", t)
                    if m:
                        candidate = m.group(1).strip()
                        # Drop common filler words at the beginning.
                        filler = {"en", "ett", "helt", "underbar", "magisk", "super", "supersmarrig", "supersmarrigt", "himla"}
                        words = [w for w in re.split(r"\s+", candidate) if w]
                        while words and words[0].lower() in filler:
                            words.pop(0)
                        candidate = " ".join(words).strip()
                        return candidate

                    # Fallback: first non-empty line, trimmed.
                    return t.split("\n", 1)[0].strip()

                title_candidate = guess_instagram_title(source_text)
                if title_candidate:
                    title = title_candidate

            # If the heading-based parser failed, fall back to the same salvage logic we use for OCR blobs.
            if not parsed_ing and not parsed_steps:
                s_title, s_desc, s_ing, s_steps = salvage_from_blob(source_text)
                if s_ing:
                    parsed_ing = s_ing
                if s_steps:
                    parsed_steps = s_steps
                if s_desc and not desc_extra:
                    desc_extra = s_desc

            # If the caption parser misclassifies and produces identical content for ingredients and steps,
            # do NOT put step text into ingredients. Instead, allow OCR to overwrite ingredients.
            # If the parsed ingredient block contains a mix of ingredients + steps, try to salvage
            # ingredient-like lines rather than discarding everything.
            if parsed_ing and parsed_steps:
                import re

                def _norm(s: str) -> str:
                    return re.sub(r"\s+", " ", (s or "").strip()).lower()

                def _split_lines(block: str) -> list[str]:
                    return [ln.strip() for ln in (block or "").splitlines() if ln.strip()]

                def _looks_like_ingredient_line(line: str) -> bool:
                    # Very rough heuristic: quantities/units or common ingredient formats.
                    s = (line or "").strip().lower()
                    if not s:
                        return False
                    # Skip subsection headings like "Sås:".
                    if s.endswith(":") and len(s) <= 30:
                        return True
                    if re.match(r"^\s*\d+(?:[\.,]\d+)?\s*(?:g|gr|kg|dl|cl|l|ml|msk|tsk|krm|st|pkt|förp|burk)\b", s):
                        return True
                    if re.match(r"^\s*\d+\s*(?:st|stycken)\b", s):
                        return True
                    if re.match(r"^\s*\d+\s*(?:-\s*\d+)?\s*(?:tsk|msk)\b", s):
                        return True
                    # Common patterns like "salt & peppar" / "salt och peppar".
                    if ("&" in s or " och " in s) and re.search(r"(?i)\b(salt|peppar|vitpeppar|svartpeppar|socker)\b", s):
                        if re.search(
                            r"(?i)\b(stek\w*|tillsätt\w*|strö\w*|servera\w*|lägg\w*|häll\w*|ringla\w*|toppa\w*|bland\w*|visp\w*|rör\w*|kok\w*|låt\w*|hack\w*|skär\w*|sätt\w*|form\w*|smak\w*|bryn\w*)\b",
                            s,
                        ):
                            return False
                        return True
                    return False

                def _looks_like_steps_block(block: str) -> bool:
                    lines = _split_lines(block)
                    if not lines:
                        return False
                    # If most lines start with verbs/emojis+verbs, it's likely steps.
                    step_like = 0
                    for ln in lines:
                        candidate = re.sub(r"^[^A-Za-zÅÄÖåäö]+", "", ln).strip()
                        if re.match(
                            r"(?i)^(stek\w*|tillsätt\w*|strö\w*|servera\w*|lägg\w*|häll\w*|ringla\w*|toppa\w*|bland\w*|visp\w*|rör\w*|kok\w*|låt\w*|hack\w*|skär\w*|sätt\w*|form\w*|smak\w*|bryn\w*)\b",
                            candidate,
                        ):
                            step_like += 1
                    return step_like >= max(2, int(len(lines) * 0.6))

                def _looks_like_step_line(line: str) -> bool:
                    s = (line or "").strip()
                    if not s:
                        return False
                    if s.startswith("(") and s.endswith(")"):
                        return False
                    s = re.sub(r"^[^A-Za-zÅÄÖåäö]+", "", s).strip()
                    return (
                        re.match(
                            r"(?i)^(stek\w*|tillsätt\w*|strö\w*|servera\w*|lägg\w*|häll\w*|ringla\w*|toppa\w*|bland\w*|visp\w*|rör\w*|kok\w*|låt\w*|hack\w*|skär\w*|sätt\w*|form\w*|smak\w*|bryn\w*)\b",
                            s,
                        )
                        is not None
                    )

                norm_ing = _norm(parsed_ing)
                norm_steps = _norm(parsed_steps)
                step_like_ing = (len(norm_ing) >= 80 and norm_ing == norm_steps) or _looks_like_steps_block(parsed_ing)
                if step_like_ing:
                    ing_lines = _split_lines(parsed_ing)
                    filtered_lines: list[str] = []
                    for ln in ing_lines:
                        # Preserve subsection headings and obvious ingredient lines.
                        if _looks_like_ingredient_line(ln):
                            filtered_lines.append(ln)
                            continue
                        # Keep short non-step lines (sometimes ingredients have no units).
                        if len(ln) <= 40 and not _looks_like_step_line(ln):
                            filtered_lines.append(ln)

                    salvaged = "\n".join(filtered_lines).strip()
                    if salvaged:
                        logger.info(
                            "Instagram caption parse produced step-like ingredients; salvaged %s ingredient lines (source_url=%s)",
                            len(filtered_lines),
                            source_url,
                        )
                        parsed_ing = salvaged
                        caption_ingredients_salvaged = True
                    else:
                        logger.info(
                            "Instagram caption parse produced step-like ingredients; no ingredient lines to salvage (source_url=%s)",
                            source_url,
                        )
                        parsed_ing = ""

                    caption_ingredients_duplicate_steps = True

            if parsed_ing and (not caption_ingredients_duplicate_steps or caption_ingredients_salvaged):
                ingredients = parsed_ing
            if parsed_steps:
                steps = parsed_steps
            if desc_extra and not description:
                description = desc_extra
        elif source_text and (not ingredients or not steps):
            parsed_ing, parsed_steps, desc_extra = parse_caption_to_recipe(source_text)
            if parsed_ing and not ingredients:
                ingredients = parsed_ing
            if parsed_steps and not steps:
                steps = parsed_steps
            if desc_extra and not description:
                description = desc_extra

        # Instagram + caption optimization can leave us with missing sections
        # when the caption doesn't include ingredients/steps but the uploaded image does.
        # Only attempt OCR fallback if an API key is configured (avoid mock data).
        if is_instagram and source_text and (
            (not ingredients or not steps) or caption_ingredients_duplicate_steps
        ):
            try:
                from .ocr_service import ImageRecipeParser

                parser = ImageRecipeParser()
                if not getattr(parser, "api_key", None):
                    logger.info(
                        "Instagram image import OCR fallback skipped (OPENAI_API_KEY missing; source_url=%s)",
                        source_url,
                    )
                else:
                    logger.info(
                        "Instagram image import OCR fallback start (source_url=%s need_ingredients=%s need_steps=%s)",
                        source_url,
                        bool((not ingredients) or caption_ingredients_duplicate_steps),
                        bool(not steps),
                    )
                    try:
                        image_file.seek(0)
                    except Exception:
                        pass
                    parsed = parser.parse_image(image_file)
                    if isinstance(parsed, dict):
                        ocr_ingredients = (parsed.get("ingredients") or "").strip()
                        ocr_steps = (parsed.get("steps") or "").strip()
                        # Fill only missing fields; keep caption-derived content when present.
                        if ocr_ingredients and (
                            (not ingredients) or caption_ingredients_duplicate_steps
                        ):
                            ingredients = ocr_ingredients
                        if ocr_steps and not steps:
                            steps = ocr_steps
                        logger.info(
                            "Instagram image import OCR fallback done (source_url=%s filled_ingredients=%s filled_steps=%s)",
                            source_url,
                            bool(ocr_ingredients and ingredients),
                            bool(ocr_steps and steps),
                        )
            except Exception:
                logger.exception("Instagram image import OCR fallback failed (non-fatal)")

        # Append source URL line for traceability (requested UX).
        if source_url:
            line = f"Originalreceptet är från {source_url}"
            if line not in (description or ""):
                if description:
                    description = f"{description}\n\n{line}"
                else:
                    description = line

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

        # Cap title to model constraint to avoid 500s from DB truncation.
        title = (title or "").strip()[:200]
        if title:
            title = title[:1].upper() + title[1:]
        if provided_title and not title:
            title = provided_title.strip()[:200]
        if not title and source_text:
            first = source_text.splitlines()[0].strip()
            title = first[:200]

        # Extract hashtags from source_text (Instagram captions) and save as tags.
        extracted_tags = ""
        if source_text:
            import re
            hashtag_pattern = r"#(\w+)"
            hashtags = re.findall(hashtag_pattern, source_text)
            if hashtags:
                # Deduplicate and clean: lowercase, unique.
                unique_tags = list(dict.fromkeys([tag.lower() for tag in hashtags]))
                extracted_tags = ", ".join(unique_tags)

        if requested_tags:
            extracted_tags = normalize_tags(",".join([extracted_tags, requested_tags]))

        recipe = Recipe.objects.create(
            user=request.user,
            title=title or "Importerad bild",
            description=description,
            ingredients=ingredients,
            steps=steps,
            cooking_time=max(1, cooking_time) if cooking_time else 30,
            servings=max(1, servings) if servings else 4,
            dish_type=dish_type or Recipe._meta.get_field("dish_type").default,
            tags=extracted_tags,
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
