from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Q
from django.contrib import messages
from .models import Recipe, WeeklyPlan, WeeklyMenu, WeeklyMenuItem, ShoppingList, ShoppingListItem, ShoppingListRecipeSource
from .forms import RecipeForm, MenuGenerationForm
from .services import add_ingredients_to_list, to_float, format_amount, upsert_shopping_list_item
import random
import requests
from bs4 import BeautifulSoup
import json
import re
import instaloader


@login_required
def shopping_lists_view(request):
    # Ensure user has a main list
    main_list = ShoppingList.objects.filter(user=request.user, is_main=True).first()
    if not main_list:
        # Try to find a suitable candidate (not recurring)
        candidate = ShoppingList.objects.filter(user=request.user, is_recurring=False).order_by('-updated_at').first()
        if candidate:
            candidate.is_main = True
            candidate.save()
            main_list = candidate
        else:
            # Create one
            main_list = ShoppingList.objects.create(user=request.user, name="Inköpslista", is_main=True)

    if request.method == 'POST' and request.POST.get('action') == 'create':
        name = (request.POST.get('name') or '').strip()
        is_recurring = request.POST.get('is_recurring') == '1'
        if name:
            lst = ShoppingList.objects.create(user=request.user, name=name, is_recurring=is_recurring, is_main=False)
            return redirect('shopping_list_detail', list_id=lst.id)

    # Get all other lists
    saved_lists = ShoppingList.objects.filter(user=request.user).exclude(id=main_list.id).order_by('-updated_at')
    
    # Annotate counts
    unchecked = ShoppingListItem.objects.filter(user=request.user, shopping_list=main_list, checked=False).count()
    main_list.unchecked_count = unchecked

    result_saved = []
    for lst in saved_lists:
        c = ShoppingListItem.objects.filter(user=request.user, shopping_list=lst, checked=False).count()
        lst.unchecked_count = c
        result_saved.append(lst)

    return render(request, 'recipes/shopping_lists.html', {'main_list': main_list, 'saved_lists': result_saved})


@login_required
def shopping_list_detail_view(request, list_id: int):
    shopping_list = get_object_or_404(ShoppingList, id=list_id, user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        if action == 'clear_all':
            ShoppingListItem.objects.filter(user=request.user, shopping_list=shopping_list).delete()
            ShoppingListRecipeSource.objects.filter(user=request.user, shopping_list=shopping_list).delete()
            messages.success(request, 'Listan rensad.')
            return redirect('shopping_list_detail', list_id=shopping_list.id)

        if action == 'clear_checked':
            ShoppingListItem.objects.filter(user=request.user, shopping_list=shopping_list, checked=True).delete()
            messages.success(request, 'Avbockade rader borttagna.')
            return redirect('shopping_list_detail', list_id=shopping_list.id)

        delete_id = request.POST.get('delete_id')
        if delete_id:
            ShoppingListItem.objects.filter(user=request.user, shopping_list=shopping_list, id=delete_id).delete()
            return redirect('shopping_list_detail', list_id=shopping_list.id)

        if request.POST.get('add_new') == '1':
            new_name = (request.POST.get('new_name') or '').strip()
            new_amount = (request.POST.get('new_amount') or '').strip()
            new_unit = (request.POST.get('new_unit') or '').strip()
            if new_name:
                upsert_shopping_list_item(request.user, shopping_list, new_name, new_amount, new_unit)
            return redirect('shopping_list_detail', list_id=shopping_list.id)
            return redirect('shopping_list_detail', list_id=shopping_list.id)

        # Save edits
        items = ShoppingListItem.objects.filter(user=request.user, shopping_list=shopping_list)
        for item in items:
            item.name = (request.POST.get(f'name_{item.id}') or '').strip() or item.name
            item.amount = (request.POST.get(f'amount_{item.id}') or '').strip()
            item.unit = (request.POST.get(f'unit_{item.id}') or '').strip()
            item.checked = request.POST.get(f'checked_{item.id}') == 'on'
            item.save(update_fields=['name', 'amount', 'unit', 'checked', 'updated_at'])

        messages.success(request, 'Listan uppdaterad.')
        return redirect('shopping_list_detail', list_id=shopping_list.id)

    items = ShoppingListItem.objects.filter(user=request.user, shopping_list=shopping_list)
    existing_names = (
        ShoppingListItem.objects.filter(user=request.user, shopping_list=shopping_list)
        .exclude(name='')
        .values_list('name', flat=True)
        .distinct()
        .order_by('name')
    )
    return render(
        request,
        'recipes/shopping_list.html',
        {'items': items, 'shopping_list': shopping_list, 'existing_names': existing_names},
    )


@login_required
def choose_shopping_list_for_recipe(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, user=request.user)

    lists = ShoppingList.objects.filter(user=request.user).order_by('-is_main', '-updated_at')

    if request.method == 'GET':
        return render(request, 'recipes/shopping_list_select.html', {'recipe': recipe, 'lists': lists})

    # POST: choose existing or create new
    list_id = (request.POST.get('list_id') or '').strip()
    new_name = (request.POST.get('new_name') or '').strip()
    new_is_recurring = request.POST.get('new_is_recurring') == '1'

    shopping_list = None
    if list_id:
        shopping_list = get_object_or_404(ShoppingList, id=list_id, user=request.user)
    elif new_name:
        shopping_list = ShoppingList.objects.create(user=request.user, name=new_name, is_recurring=new_is_recurring)
    else:
        messages.error(request, 'Välj en lista eller ange namn för en ny.')
        return redirect('choose_shopping_list_for_recipe', pk=recipe.pk)

    return _add_recipe_ingredients_to_shopping_list(request, recipe, shopping_list)


def _add_recipe_ingredients_to_shopping_list(request, recipe: Recipe, shopping_list: ShoppingList):
    result = add_ingredients_to_list(request.user, recipe, shopping_list)
    
    if result['already_exists']:
        messages.info(request, 'Ingredienser från det här receptet är redan tillagda i den valda listan.')
    elif result['added'] or result['merged']:
        msg = f"La till {result['added']} ingredienser."
        if result['merged']:
            msg += f" Slog ihop {result['merged']} rader."
        messages.success(request, msg)
    else:
        messages.info(request, 'Inga ingredienser att lägga till.')

    return redirect('shopping_list_detail', list_id=shopping_list.id)

def parse_recipe_text(text):
    """Parse raw text to extract title, ingredients and steps."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    title = ""
    ingredients = []
    steps = []
    
    if not lines:
        return title, ingredients, steps
        
    # Guess title from first line
    title = lines[0]
    if len(title) > 100:
        title = title[:97] + "..."
    
    # Keywords
    ing_start = ['ingredienser', 'ingredients', 'shopping list', 'behöver', 'innehåll', 'du behöver']
    step_start = ['gör så här', 'instruktioner', 'instructions', 'steps', 'tillagning', 'utförande', 'därefter', 'så här gör du']
    
    current_mode = 'unknown'
    
    for line in lines[1:]: # Skip title
        lower = line.lower()
        
        # Check for section headers
        is_header = False
        for k in ing_start:
            if k in lower and len(line) < 40: # Header should be short
                current_mode = 'ingredients'
                is_header = True
                break
        if is_header: continue
        
        for k in step_start:
            if k in lower and len(line) < 40:
                current_mode = 'steps'
                is_header = True
                break
        if is_header: continue
        
        # Add content based on mode
        if current_mode == 'ingredients':
            ingredients.append(line)
        elif current_mode == 'steps':
            steps.append(line)
        else:
            # Heuristics if no header found yet
            # Ingredients often start with -, *, or digit
            if re.match(r'^[-*•\d½⅓¼]', line):
                ingredients.append(line)
                if current_mode == 'unknown':
                    current_mode = 'ingredients' # Switch to ingredients mode if we see a list
            elif len(line) > 50:
                # Long lines might be steps
                if current_mode == 'unknown':
                    # If we haven't found ingredients yet, treat as description/steps
                    steps.append(line)
                
    return title, ingredients, steps

def parse_iso_duration(duration_str):
    """Parse ISO 8601 duration string (e.g., PT1H30M) to minutes."""
    if not duration_str:
        return 0
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', duration_str)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes

def extract_json_ld(soup):
    """Extract recipe data from JSON-LD."""
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            data = json.loads(script.string)
            # JSON-LD can be a list or a dict, and can have a graph
            nodes = []
            if isinstance(data, dict):
                if '@graph' in data:
                    nodes = data['@graph']
                else:
                    nodes = [data]
            elif isinstance(data, list):
                nodes = data
            
            for node in nodes:
                if node.get('@type') == 'Recipe' or 'Recipe' in node.get('@type', []):
                    return node
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _flatten_instruction_texts(node):
    """Flatten JSON-LD recipeInstructions into a list of step strings."""
    steps: list[str] = []

    def add_text(value):
        if value is None:
            return
        if isinstance(value, str):
            v = value.strip()
            if v:
                steps.append(v)
            return
        if isinstance(value, list):
            for item in value:
                add_text(item)
            return
        if isinstance(value, dict):
            # Common patterns:
            # - HowToStep: {"@type":"HowToStep","text":"..."}
            # - HowToSection: {"@type":"HowToSection","itemListElement":[...]}
            # - itemListElement can also appear without explicit @type.
            if 'text' in value:
                add_text(value.get('text'))
                return

            if 'itemListElement' in value:
                add_text(value.get('itemListElement'))
                return

            # Fallback: try a few commonly used keys.
            for key in ('name', 'description'):
                if key in value:
                    add_text(value.get(key))
                    return

    add_text(node)
    # Deduplicate empty lines while preserving order
    return [s for s in steps if s]

class RecipeListView(LoginRequiredMixin, ListView):
    model = Recipe
    template_name = 'recipes/recipe_list.html'
    context_object_name = 'recipes'

    def get_queryset(self):
        queryset = Recipe.objects.filter(user=self.request.user)
        
        # Search
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(title__icontains=q)
        
        # Filters
        dish_type = self.request.GET.get('type')
        if dish_type:
            queryset = queryset.filter(dish_type=dish_type)
            
        difficulty = self.request.GET.get('difficulty')
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)
            
        max_time = self.request.GET.get('max_time')
        if max_time:
            queryset = queryset.filter(cooking_time__lte=max_time)
            
        favorites = self.request.GET.get('favorites')
        if favorites:
            queryset = queryset.filter(is_favorite=True)
            
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['type_choices'] = Recipe.TYPE_CHOICES
        context['difficulty_choices'] = Recipe.DIFFICULTY_CHOICES
        return context

class RecipeDetailView(LoginRequiredMixin, DetailView):
    model = Recipe
    template_name = 'recipes/recipe_detail.html'

    def get_queryset(self):
        return Recipe.objects.filter(user=self.request.user)

class RecipeCookView(LoginRequiredMixin, DetailView):
    model = Recipe
    template_name = 'recipes/recipe_cook.html'

    def get_queryset(self):
        return Recipe.objects.filter(user=self.request.user)

def get_all_ingredient_names(user):
    """Helper to get all unique ingredient names from user's recipes."""
    recipes = Recipe.objects.filter(user=user)
    names = set()
    for r in recipes:
        try:
            # Try to parse as JSON
            data = json.loads(r.ingredients)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'name' in item:
                        names.add(item['name'])
        except (json.JSONDecodeError, TypeError):
            pass
    return sorted(list(names))

from django.core.files.base import ContentFile

class RecipeCreateView(LoginRequiredMixin, CreateView):
    model = Recipe
    form_class = RecipeForm
    template_name = 'recipes/recipe_form.html'
    success_url = reverse_lazy('recipe_list')

    def get_initial(self):
        initial = super().get_initial()
        
        # Default values
        initial['cooking_time'] = 30
        
        # Check for session data (from server-side import)
        # Don't pop it yet, we might need it in get_context_data
        import_data = self.request.session.get('import_data', None)
        if import_data:
            initial.update(import_data)
            
        # Check for GET parameters (from Bookmarklet/Extension)
        title = self.request.GET.get('title')
        if title:
            initial['title'] = title
            
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass import data to template for the helper tool
        import_data = self.request.session.pop('import_data', None)
        if import_data:
            context['imported_text'] = import_data.get('imported_text')
            context['imported_image_url'] = import_data.get('imported_image_url')
        
        # Add ingredient autocomplete list
        context['all_ingredients'] = get_all_ingredient_names(self.request.user)
        return context

    def form_valid(self, form):
        form.instance.user = self.request.user
        
        # Handle image download if requested
        imported_image_url = self.request.POST.get('imported_image_url')
        save_image = self.request.POST.get('save_imported_image') == 'on'
        
        if imported_image_url and save_image:
            try:
                response = requests.get(imported_image_url, timeout=10)
                if response.status_code == 200:
                    # Create a filename
                    filename = f"imported_image_{random.randint(1000, 9999)}.jpg"
                    form.instance.image.save(filename, ContentFile(response.content), save=False)
            except Exception as e:
                print(f"Failed to download image: {e}")
                
        return super().form_valid(form)

class RecipeUpdateView(LoginRequiredMixin, UpdateView):
    model = Recipe
    form_class = RecipeForm
    template_name = 'recipes/recipe_form.html'
    success_url = reverse_lazy('recipe_list')

    def get_queryset(self):
        return Recipe.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_ingredients'] = get_all_ingredient_names(self.request.user)
        return context

class RecipeDeleteView(LoginRequiredMixin, DeleteView):
    model = Recipe
    template_name = 'recipes/recipe_confirm_delete.html'
    success_url = reverse_lazy('recipe_list')

    def get_queryset(self):
        return Recipe.objects.filter(user=self.request.user)

@login_required
def weekly_plan_view(request):
    weekly_plan = WeeklyPlan.objects.filter(user=request.user)
    plan_dict = {item.day: item for item in weekly_plan}
    all_recipes = Recipe.objects.filter(user=request.user)
    
    form = MenuGenerationForm()

    context = {
        'weekly_plan': plan_dict,
        'days': WeeklyPlan.DAYS_OF_WEEK,
        'all_recipes': all_recipes,
        'form': form,
    }
    return render(request, 'recipes/weekly_plan.html', context)

@login_required
def update_menu_day(request):
    if request.method == 'POST':
        day = request.POST.get('day')
        recipe_id = request.POST.get('recipe_id')
        
        if day and recipe_id:
            recipe = get_object_or_404(Recipe, pk=recipe_id, user=request.user)
            WeeklyPlan.objects.update_or_create(
                user=request.user,
                day=day,
                defaults={'recipe': recipe}
            )
    return redirect('weekly_plan')

@login_required
def remove_from_menu(request, pk):
    if request.method == 'POST':
        item = get_object_or_404(WeeklyPlan, pk=pk, user=request.user)
        item.delete()
    return redirect('weekly_plan')

@login_required
def generate_random_menu(request):
    if request.method == 'POST':
        form = MenuGenerationForm(request.POST)
        if form.is_valid():
            servings = form.cleaned_data.get('servings', 4)
            max_time = form.cleaned_data.get('max_cooking_time')
            include_types = form.cleaned_data.get('include_types')
            exclude_types = form.cleaned_data.get('exclude_types')

            queryset = Recipe.objects.filter(user=request.user)

            if max_time:
                queryset = queryset.filter(cooking_time__lte=max_time)
            
            is_default_filter = False
            if include_types:
                queryset = queryset.filter(dish_type__in=include_types)
            else:
                # Default to lunch/dinner if no types specified
                queryset = queryset.filter(dish_type='lunch_dinner')
                is_default_filter = True
            
            if exclude_types:
                queryset = queryset.exclude(dish_type__in=exclude_types)

            recipes = list(queryset)
            
            if not recipes:
                if is_default_filter:
                    messages.error(request, "Inga lunch-/middagsrecept hittades. Kategorisera dina recept som 'Lunch/Middag' eller välj andra typer.")
                else:
                    messages.error(request, "Inga recept matchade dina kriterier.")
                return redirect('weekly_plan')

            # Clear existing
            WeeklyPlan.objects.filter(user=request.user).delete()

            if len(recipes) >= 7:
                selected_recipes = random.sample(recipes, 7)
            else:
                # Allow duplicates if not enough recipes
                selected_recipes = [random.choice(recipes) for _ in range(7)]
                
            days = [d[0] for d in WeeklyPlan.DAYS_OF_WEEK]
            
            for day, recipe in zip(days, selected_recipes):
                WeeklyPlan.objects.create(user=request.user, day=day, recipe=recipe, servings=servings)
            
            messages.success(request, f"Veckomeny skapad för {servings} portioner!")
            
    return redirect('weekly_plan')

@login_required
def clear_menu(request):
    if request.method == 'POST':
        WeeklyPlan.objects.filter(user=request.user).delete()
    return redirect('weekly_plan')


@login_required
def save_weekly_menu(request):
    if request.method != 'POST':
        return redirect('weekly_plan')

    items = list(WeeklyPlan.objects.filter(user=request.user).select_related('recipe'))
    if not items:
        messages.error(request, "Ingen veckomeny att spara.")
        return redirect('weekly_plan')

    name = (request.POST.get('menu_name') or '').strip()

    # Default: next ISO week number (Monday start)
    from datetime import date, timedelta

    next_week = date.today() + timedelta(days=7)
    iso = next_week.isocalendar()
    week_number = int(iso.week)
    year = int(iso.year)

    if not name:
        name = f"Vecka {week_number}"

    # Use servings from the first item, or default to 4
    servings = items[0].servings if items else 4

    # Append servings to name
    name = f"{name} ({servings}p)"

    menu = WeeklyMenu.objects.create(
        user=request.user,
        name=name,
        week_number=week_number,
        year=year,
        servings=servings,
    )

    for it in items:
        WeeklyMenuItem.objects.create(menu=menu, day=it.day, recipe=it.recipe)

    messages.success(request, f"Sparade veckomeny: {menu.name}")
    return redirect('weekly_plan')

@login_required
def recipe_import(request):
    if request.method == 'POST':
        url = request.POST.get('url')
        recipe_text = request.POST.get('recipe_text')
        
        if recipe_text:
            # Handle text import
            title, ingredients, steps = parse_recipe_text(recipe_text)
            
            initial_data = {
                'title': title,
                'description': f"{recipe_text[:500]}...",
                'ingredients': '\n'.join(ingredients),
                'steps': '\n'.join(steps),
            }
            request.session['import_data'] = initial_data
            return redirect('recipe_create')
            
        elif url:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # Special handling for Instagram
            if 'instagram.com' in url:
                try:
                    L = instaloader.Instaloader()
                    # Extract shortcode
                    match = re.search(r'/(?:p|reel)/([^/?#&]+)', url)
                    if match:
                        shortcode = match.group(1)
                        post = instaloader.Post.from_shortcode(L.context, shortcode)
                        
                        # Use the caption as the source text
                        full_text = post.caption or ""
                        
                        # Simplified Import: Just Title, Image, Link and Full Text
                        # We skip the advanced parsing for now as it is unreliable for video captions
                        
                        # Title: First line or Username
                        title_line = full_text.split('\n')[0] if full_text else f"Recept från {post.owner_username}"
                        if len(title_line) > 100:
                            title_line = title_line[:97] + "..."
                            
                        initial_data = {
                            'title': title_line,
                            'description': "", # Keep description clean
                            'ingredients': '',
                            'steps': '',
                            'imported_text': full_text, # Raw text for the helper tool
                            'imported_image_url': post.url # URL for the image downloader
                        }

                        request.session['import_data'] = initial_data
                        return redirect('recipe_create')
                except Exception as e:
                    # Fallback to standard scraping if instaloader fails
                    print(f"Instaloader failed: {e}")
                    pass
                    print(f"Instaloader failed: {e}")
                    pass

            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

                def fetch(fetch_url: str):
                    resp = requests.get(fetch_url, headers=headers, timeout=10)
                    resp.raise_for_status()
                    return resp

                try:
                    response = fetch(url)
                except requests.RequestException as e:
                    retry_succeeded = False
                    # Retry with www if not present
                    if 'www.' not in url:
                        try:
                            url_parts = url.split('://')
                            url_www = f"{url_parts[0]}://www.{url_parts[1]}"
                            response = fetch(url_www)
                            url = url_www
                            retry_succeeded = True
                        except requests.RequestException as e2:
                            e = e2

                    if not retry_succeeded:
                        # Give a user-friendly error message.
                        if isinstance(e, requests.Timeout):
                            messages.error(request, "Kunde inte hämta recept: Tidsgränsen överskreds. Prova igen eller testa en annan länk.")
                            return render(request, 'recipes/recipe_import.html')
                        if isinstance(e, requests.ConnectionError):
                            messages.error(request, "Kunde inte hämta recept: Kunde inte ansluta till sidan. Kontrollera att länken fungerar och prova igen.")
                            return render(request, 'recipes/recipe_import.html')
                        if isinstance(e, requests.HTTPError):
                            status_code = getattr(getattr(e, 'response', None), 'status_code', None)
                            if status_code:
                                messages.error(request, f"Kunde inte hämta recept: Sidan svarade med HTTP {status_code}.")
                            else:
                                messages.error(request, "Kunde inte hämta recept: Sidan svarade med ett fel.")
                            return render(request, 'recipes/recipe_import.html')

                        messages.error(request, "Kunde inte hämta recept: Okänt nätverksfel. Prova igen eller testa en annan länk.")
                        return render(request, 'recipes/recipe_import.html')

                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Default values
                title = soup.title.string if soup.title else ''
                description = ''
                ingredients = []
                steps = []
                cooking_time = 0
                servings = 4
                image_url = ''
                
                # Try JSON-LD first (Best quality)
                recipe_data = extract_json_ld(soup)
                
                if recipe_data:
                    title = recipe_data.get('name', title)
                    description = recipe_data.get('description', '')
                    
                    # Ingredients
                    raw_ingredients = recipe_data.get('recipeIngredient', [])
                    if isinstance(raw_ingredients, list):
                        ingredients = raw_ingredients
                    elif isinstance(raw_ingredients, str):
                        ingredients = [raw_ingredients]
                        
                    # Instructions
                    raw_instructions = recipe_data.get('recipeInstructions', [])
                    steps = _flatten_instruction_texts(raw_instructions)
                        
                    # Time
                    total_time = recipe_data.get('totalTime')
                    cook_time = recipe_data.get('cookTime')
                    prep_time = recipe_data.get('prepTime')
                    
                    if total_time:
                        cooking_time = parse_iso_duration(total_time)
                    elif cook_time or prep_time:
                        cooking_time = parse_iso_duration(cook_time) + parse_iso_duration(prep_time)
                        
                    # Servings (often string like "4 servings")
                    yield_data = recipe_data.get('recipeYield')
                    if yield_data:
                        if isinstance(yield_data, list):
                            yield_data = yield_data[0]
                        match = re.search(r'(\d+)', str(yield_data))
                        if match:
                            servings = int(match.group(1))
                            
                    # Image
                    img_data = recipe_data.get('image')
                    if isinstance(img_data, list):
                        image_url = img_data[0] if img_data else ''
                    elif isinstance(img_data, dict):
                        image_url = img_data.get('url', '')
                    elif isinstance(img_data, str):
                        image_url = img_data

                else:
                    # Fallback to basic scraping
                    og_image = soup.find('meta', property='og:image')
                    if og_image:
                        image_url = og_image.get('content', '')
                    
                    og_description = soup.find('meta', property='og:description')
                    if og_description:
                        description = og_description.get('content', '')
                    
                    og_title = soup.find('meta', property='og:title')
                    if og_title:
                        # If title is generic or empty, use og:title
                        if not title or title.lower() in ['instagram', 'facebook', 'log in']:
                            title = og_title.get('content', '')
                            # Cleanup Instagram title
                            if ' on Instagram: "' in title:
                                parts = title.split(' on Instagram: "')
                                if len(parts) > 1:
                                    # Use the start of the caption as title, or just the author?
                                    # Often the caption starts with the recipe name.
                                    # Let's keep it simple for now, maybe just take the first line of the caption if possible
                                    caption = parts[1].rstrip('"')
                                    title = caption.split('\n')[0][:100] # First line, max 100 chars
                                    if not description:
                                        description = caption

                    if not description:
                        paragraphs = [p.get_text().strip() for p in soup.find_all('p') if len(p.get_text().strip()) > 30]
                        description = '\n\n'.join(paragraphs[:3])
                
                # Prepare data for form
                initial_data = {
                    'title': title.strip(),
                    'description': f"{description[:1000]}",
                    'ingredients': '\n'.join(ingredients),
                    'steps': '\n'.join(steps),
                    'cooking_time': cooking_time,
                    'servings': servings,
                }

                if not initial_data['title'] and not initial_data['ingredients'].strip() and not initial_data['steps'].strip():
                    messages.error(request, "Kunde inte hämta recept: Hittade inget recept-innehåll på sidan. Prova en annan länk eller skapa receptet manuellt.")
                    return render(request, 'recipes/recipe_import.html')
                

                # Pass image URL through to the create form so the user can choose to save it.
                if image_url:
                    initial_data['imported_image_url'] = image_url
                
                request.session['import_data'] = initial_data
                return redirect('recipe_create')
                
            except Exception as e:
                messages.error(request, f"Kunde inte hämta recept: {str(e)}")
    
    return render(request, 'recipes/recipe_import.html')

@login_required
def recipe_import_image(request):
    if request.method == 'POST':
        image_file = request.FILES.get('recipe_image')
        if image_file:
            from .ocr_service import ImageRecipeParser
            parser = ImageRecipeParser()
            
            # Parse image
            data = parser.parse_image(image_file)
            
            # Save to session
            request.session['import_data'] = data
            
            # We might want to save the image temporarily to show it in the create view?
            # For now, let's just pass the text data.
            # Ideally, we would save the image to a temp location and pass the path,
            # so the user can attach it to the recipe.
            
            return redirect('recipe_create')
            
    return render(request, 'recipes/recipe_import_image.html')

@login_required
def add_weekly_menu_to_shopping_list(request):
    if request.method == 'POST':
        # Get main shopping list
        shopping_list = ShoppingList.objects.filter(user=request.user, is_main=True).first()
        if not shopping_list:
            shopping_list = ShoppingList.objects.create(user=request.user, name="Inköpslista", is_main=True)
        
        weekly_plan = WeeklyPlan.objects.filter(user=request.user)
        if not weekly_plan:
            messages.info(request, "Ingen veckomeny att lägga till.")
            return redirect('weekly_plan')
            
        total_added = 0
        total_merged = 0
        
        for item in weekly_plan:
            # We use force=True to allow adding even if the recipe is already in the list
            result = add_ingredients_to_list(request.user, item.recipe, shopping_list, target_servings=item.servings, force=True)
            total_added += result['added']
            total_merged += result['merged']
            
        messages.success(request, f"La till {total_added} ingredienser och uppdaterade {total_merged} rader i inköpslistan.")
        return redirect('shopping_list_detail', list_id=shopping_list.id)
        
    return redirect('weekly_plan')

@login_required
def bookmarklet_view(request):
    return render(request, 'recipes/bookmarklet.html')
