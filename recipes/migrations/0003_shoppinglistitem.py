from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0002_alter_recipe_options_alter_weeklyplan_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShoppingListItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Ingrediens')),
                ('amount', models.CharField(blank=True, max_length=50, verbose_name='Mängd')),
                ('unit', models.CharField(blank=True, max_length=20, verbose_name='Enhet')),
                ('checked', models.BooleanField(default=False, verbose_name='Avbockad')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Skapad')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Uppdaterad')),
                ('recipe', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='recipes.recipe', verbose_name='Källa (recept)')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Användare')),
            ],
            options={
                'verbose_name': 'Inköpsrad',
                'verbose_name_plural': 'Inköpsrader',
                'ordering': ['checked', '-updated_at', '-created_at'],
            },
        ),
    ]
