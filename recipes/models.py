from django.db import models
from django.contrib.auth.models import User

class Recipe(models.Model):
    """
    Represents a user-created recipe with metadata, ingredients, steps, and optional image.
    Linked to a user and can be categorized by type, difficulty, and tags.
    """
    DIFFICULTY_CHOICES = [
        ('easy', 'Enkel'),
        ('medium', 'Medel'),
        ('hard', 'Avancerad'),
    ]
    
    TYPE_CHOICES = [
        ('breakfast', 'Frukost'),
        ('lunch_dinner', 'Lunch/Middag'),
        ('appetizer', 'Förrätt'),
        ('dessert', 'Efterrätt'),
        ('snack', 'Mellanmål'),
        ('party', 'Fest'),
        ('vegetarian', 'Vegetariskt'),
        ('other', 'Övrigt'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Användare")  # Owner of the recipe
    title = models.CharField(max_length=200, verbose_name="Titel")
    description = models.TextField(blank=True, verbose_name="Beskrivning")
    ingredients = models.TextField(help_text="Lista ingredienser, en per rad", verbose_name="Ingredienser")  # One ingredient per line
    steps = models.TextField(help_text="Beskriv tillagningsstegen", verbose_name="Gör så här")  # Preparation steps
    cooking_time = models.PositiveIntegerField(help_text="Tid i minuter", verbose_name="Tillagningstid")
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium', verbose_name="Svårighetsgrad")
    dish_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='lunch_dinner', verbose_name="Typ av rätt")
    tags = models.CharField(max_length=200, blank=True, help_text="Kommaseparerade taggar", verbose_name="Taggar")
    servings = models.PositiveIntegerField(default=4, verbose_name="Antal portioner")
    image = models.ImageField(upload_to='recipes/', blank=True, null=True, verbose_name="Bild")  # Optional uploaded image
    image_url = models.URLField(blank=True, null=True, verbose_name="Bild-URL")  # Optional external image URL
    is_favorite = models.BooleanField(default=False, verbose_name="Favorit")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Skapad")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Uppdaterad")

    class Meta:
        verbose_name = "Recept"
        verbose_name_plural = "Recept"

    def __str__(self):
        return self.title


class Cookbook(models.Model):
    """A user-owned cookbook (collection of recipes)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Användare")
    name = models.CharField(max_length=120, verbose_name="Namn")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Skapad")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Uppdaterad")

    recipes = models.ManyToManyField(
        Recipe,
        through='CookbookRecipe',
        related_name='cookbooks',
        blank=True,
    )

    class Meta:
        verbose_name = "Kokbok"
        verbose_name_plural = "Kokböcker"
        ordering = ['-updated_at', '-created_at']
        unique_together = ('user', 'name')

    def __str__(self):
        return self.name


class CookbookRecipe(models.Model):
    cookbook = models.ForeignKey(Cookbook, on_delete=models.CASCADE, related_name='cookbook_recipes')
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='cookbook_recipes')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Skapad")

    class Meta:
        verbose_name = "Kokbok-recept"
        verbose_name_plural = "Kokbok-recept"
        unique_together = ('cookbook', 'recipe')

    def __str__(self):
        return f"{self.cookbook.name}: {self.recipe.title}"

class WeeklyPlan(models.Model):
    """
    Represents a user's plan for a specific day of the week, linking a recipe to a day.
    Used for weekly meal planning.
    """
    DAYS_OF_WEEK = [
        ('mon', 'Måndag'),
        ('tue', 'Tisdag'),
        ('wed', 'Onsdag'),
        ('thu', 'Torsdag'),
        ('fri', 'Fredag'),
        ('sat', 'Lördag'),
        ('sun', 'Söndag'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Användare")  # Owner of the plan
    day = models.CharField(max_length=3, choices=DAYS_OF_WEEK, verbose_name="Dag")
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, verbose_name="Recept")  # Recipe for the day
    servings = models.PositiveIntegerField(default=4, verbose_name="Antal portioner")

    class Meta:
        unique_together = ('user', 'day', 'recipe')
        verbose_name = "Veckoplan"
        verbose_name_plural = "Veckoplaner"

    def __str__(self):
        return f"{self.user.username} - {self.day}: {self.recipe.title}"


class WeeklyMenu(models.Model):
    """
    Represents a saved weekly menu, which can be reused or referenced later.
    Contains a name, week number, year, and servings.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Användare")  # Owner of the menu
    name = models.CharField(max_length=120, verbose_name="Namn")
    week_number = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Veckonummer")
    year = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="År")
    servings = models.PositiveIntegerField(default=4, verbose_name="Antal portioner")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Skapad")

    class Meta:
        verbose_name = "Veckomeny"
        verbose_name_plural = "Veckomenyer"
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class WeeklyMenuItem(models.Model):
    """
    Represents a single day/recipe entry in a WeeklyMenu.
    Links a menu, a day, and a recipe.
    """
    menu = models.ForeignKey(WeeklyMenu, on_delete=models.CASCADE, related_name='items', verbose_name="Veckomeny")  # Parent menu
    day = models.CharField(max_length=3, choices=WeeklyPlan.DAYS_OF_WEEK, verbose_name="Dag")
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, verbose_name="Recept")  # Recipe for the day

    class Meta:
        verbose_name = "Veckomeny-rad"
        verbose_name_plural = "Veckomeny-rader"
        unique_together = ('menu', 'day')

    def __str__(self):
        return f"{self.menu.name} - {self.day}: {self.recipe.title}"


class ShoppingList(models.Model):
    """
    Represents a shopping list for a user.
    Can be marked as recurring or as the user's main list.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Användare")  # Owner of the list
    name = models.CharField(max_length=120, verbose_name="Namn")
    is_recurring = models.BooleanField(default=False, verbose_name="Återkommande")  # If true, list is recurring
    is_main = models.BooleanField(default=False, verbose_name="Huvudlista")  # If true, this is the user's main list
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Skapad")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Uppdaterad")

    class Meta:
        verbose_name = "Inköpslista"
        verbose_name_plural = "Inköpslistor"
        ordering = ['-updated_at', '-created_at']

    def __str__(self):
        return self.name


class ShoppingListItem(models.Model):
    """
    Represents an item (ingredient) in a shopping list.
    Optionally linked to a recipe as its source.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Användare")  # Owner of the item
    shopping_list = models.ForeignKey('ShoppingList', on_delete=models.CASCADE, verbose_name="Inköpslista", related_name='items', null=True, blank=True)  # Parent list
    recipe = models.ForeignKey(Recipe, on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Källa (recept)")  # Source recipe (optional)

    name = models.CharField(max_length=255, verbose_name="Ingrediens")  # Ingredient name
    amount = models.CharField(max_length=50, blank=True, verbose_name="Mängd")  # Quantity
    unit = models.CharField(max_length=20, blank=True, verbose_name="Enhet")  # Unit (e.g., g, ml)
    checked = models.BooleanField(default=False, verbose_name="Avbockad")  # Marked as purchased

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Skapad")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Uppdaterad")

    class Meta:
        verbose_name = "Inköpsrad"
        verbose_name_plural = "Inköpsrader"
        ordering = ['checked', 'name', '-updated_at', '-created_at']

    def __str__(self):
        return f"{self.name}"


class ShoppingListRecipeSource(models.Model):
    """
    Tracks which recipes have contributed ingredients to a shopping list.
    Used to prevent duplicate imports and for traceability.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Användare")  # Owner
    shopping_list = models.ForeignKey('ShoppingList', on_delete=models.CASCADE, verbose_name="Inköpslista", related_name='sources', null=True, blank=True)  # Target list
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, verbose_name="Recept")  # Source recipe
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Skapad")

    class Meta:
        verbose_name = "Inköpslista-källa"
        verbose_name_plural = "Inköpslista-källor"
        unique_together = ('user', 'shopping_list', 'recipe')

    def __str__(self):
        return f"{self.user.username}: {self.recipe.title}"
