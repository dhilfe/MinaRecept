from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
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


class EmailSignupForm(forms.Form):
    """Minimal signup (email + password) without needing social/OAuth setup.

    We keep Django's default User model and store email in both `User.email` and
    `User.username` so the existing LoginView (username/password) continues to work.
    """

    email = forms.EmailField(
        label='E-post',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
    )
    password1 = forms.CharField(
        label='Lösenord',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Upprepa lösenord',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email:
            raise ValidationError('E-post är obligatoriskt.')

        # Enforce uniqueness at app level (default Django User does not require unique email).
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise ValidationError('E-postadressen används redan.')
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')

        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Lösenorden matchar inte.')

        if password1:
            validate_password(password1)

        return cleaned

    def save(self) -> User:
        email = self.cleaned_data['email']
        password = self.cleaned_data['password1']
        return User.objects.create_user(username=email, email=email, password=password)
