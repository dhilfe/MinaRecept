from django.db import models
from django.contrib.auth.models import User

class Recipe(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Enkel'),
        ('medium', 'Medel'),
        ('hard', 'Avancerad'),
    ]
    
    TYPE_CHOICES = [
        ('everyday', 'Vardagsmat'),
        ('party', 'Fest'),
        ('dessert', 'Efterrätt'),
        ('vegetarian', 'Vegetariskt'),
        ('other', 'Övrigt'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Användare")
    title = models.CharField(max_length=200, verbose_name="Titel")
    description = models.TextField(blank=True, verbose_name="Beskrivning")
    ingredients = models.TextField(help_text="Lista ingredienser, en per rad", verbose_name="Ingredienser")
    steps = models.TextField(help_text="Beskriv tillagningsstegen", verbose_name="Gör så här")
    cooking_time = models.PositiveIntegerField(help_text="Tid i minuter", verbose_name="Tillagningstid")
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium', verbose_name="Svårighetsgrad")
    dish_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='everyday', verbose_name="Typ av rätt")
    tags = models.CharField(max_length=200, blank=True, help_text="Kommaseparerade taggar", verbose_name="Taggar")
    servings = models.PositiveIntegerField(default=4, verbose_name="Antal portioner")
    image = models.ImageField(upload_to='recipes/', blank=True, null=True, verbose_name="Bild")
    is_favorite = models.BooleanField(default=False, verbose_name="Favorit")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Skapad")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Uppdaterad")

    class Meta:
        verbose_name = "Recept"
        verbose_name_plural = "Recept"

    def __str__(self):
        return self.title

class WeeklyPlan(models.Model):
    DAYS_OF_WEEK = [
        ('mon', 'Måndag'),
        ('tue', 'Tisdag'),
        ('wed', 'Onsdag'),
        ('thu', 'Torsdag'),
        ('fri', 'Fredag'),
        ('sat', 'Lördag'),
        ('sun', 'Söndag'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Användare")
    day = models.CharField(max_length=3, choices=DAYS_OF_WEEK, verbose_name="Dag")
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, verbose_name="Recept")

    class Meta:
        unique_together = ('user', 'day', 'recipe')
        verbose_name = "Veckoplan"
        verbose_name_plural = "Veckoplaner"

    def __str__(self):
        return f"{self.user.username} - {self.day}: {self.recipe.title}"


class WeeklyMenu(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Användare")
    name = models.CharField(max_length=120, verbose_name="Namn")
    week_number = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Veckonummer")
    year = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="År")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Skapad")

    class Meta:
        verbose_name = "Veckomeny"
        verbose_name_plural = "Veckomenyer"
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class WeeklyMenuItem(models.Model):
    menu = models.ForeignKey(WeeklyMenu, on_delete=models.CASCADE, related_name='items', verbose_name="Veckomeny")
    day = models.CharField(max_length=3, choices=WeeklyPlan.DAYS_OF_WEEK, verbose_name="Dag")
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, verbose_name="Recept")

    class Meta:
        verbose_name = "Veckomeny-rad"
        verbose_name_plural = "Veckomeny-rader"
        unique_together = ('menu', 'day')

    def __str__(self):
        return f"{self.menu.name} - {self.day}: {self.recipe.title}"


class ShoppingList(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Användare")
    name = models.CharField(max_length=120, verbose_name="Namn")
    is_recurring = models.BooleanField(default=False, verbose_name="Återkommande")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Skapad")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Uppdaterad")

    class Meta:
        verbose_name = "Inköpslista"
        verbose_name_plural = "Inköpslistor"
        ordering = ['-updated_at', '-created_at']

    def __str__(self):
        return self.name


class ShoppingListItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Användare")
    shopping_list = models.ForeignKey('ShoppingList', on_delete=models.CASCADE, verbose_name="Inköpslista", related_name='items', null=True, blank=True)
    recipe = models.ForeignKey(Recipe, on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Källa (recept)")

    name = models.CharField(max_length=255, verbose_name="Ingrediens")
    amount = models.CharField(max_length=50, blank=True, verbose_name="Mängd")
    unit = models.CharField(max_length=20, blank=True, verbose_name="Enhet")
    checked = models.BooleanField(default=False, verbose_name="Avbockad")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Skapad")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Uppdaterad")

    class Meta:
        verbose_name = "Inköpsrad"
        verbose_name_plural = "Inköpsrader"
        ordering = ['checked', 'name', '-updated_at', '-created_at']

    def __str__(self):
        return f"{self.name}"


class ShoppingListRecipeSource(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Användare")
    shopping_list = models.ForeignKey('ShoppingList', on_delete=models.CASCADE, verbose_name="Inköpslista", related_name='sources', null=True, blank=True)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, verbose_name="Recept")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Skapad")

    class Meta:
        verbose_name = "Inköpslista-källa"
        verbose_name_plural = "Inköpslista-källor"
        unique_together = ('user', 'shopping_list', 'recipe')

    def __str__(self):
        return f"{self.user.username}: {self.recipe.title}"
