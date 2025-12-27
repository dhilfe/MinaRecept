from django import forms
from .models import Recipe

class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = ['title', 'ingredients', 'steps', 'cooking_time', 'difficulty', 'dish_type', 'tags', 'servings', 'image', 'is_favorite']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'ingredients': forms.HiddenInput(), # Hidden, handled by JS
            'steps': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'cooking_time': forms.NumberInput(attrs={'class': 'form-control', 'step': '5', 'style': 'width: 120px;'}),
            'difficulty': forms.Select(attrs={'class': 'form-select', 'style': 'width: 150px;'}),
            'dish_type': forms.Select(attrs={'class': 'form-select', 'style': 'width: 150px;'}),
            'tags': forms.TextInput(attrs={'class': 'form-control'}),
            'servings': forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 150px;'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'is_favorite': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class MenuGenerationForm(forms.Form):
    servings = forms.IntegerField(
        initial=4,
        label="Antal portioner",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    max_cooking_time = forms.IntegerField(
        required=False, 
        label="Max tillagningstid (min)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    include_types = forms.MultipleChoiceField(
        choices=Recipe.TYPE_CHOICES,
        required=False,
        label="Inkludera typer",
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    exclude_types = forms.MultipleChoiceField(
        choices=Recipe.TYPE_CHOICES,
        required=False,
        label="Exkludera typer",
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
