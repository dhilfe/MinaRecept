from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def forwards(apps, schema_editor):
    ShoppingList = apps.get_model('recipes', 'ShoppingList')
    ShoppingListItem = apps.get_model('recipes', 'ShoppingListItem')
    ShoppingListRecipeSource = apps.get_model('recipes', 'ShoppingListRecipeSource')

    # Create a default list per user that has either items or sources
    user_ids = set(ShoppingListItem.objects.values_list('user_id', flat=True)) | set(
        ShoppingListRecipeSource.objects.values_list('user_id', flat=True)
    )

    for user_id in user_ids:
        default_list, _ = ShoppingList.objects.get_or_create(
            user_id=user_id,
            name='Inköpslista',
            defaults={'is_recurring': False},
        )
        ShoppingListItem.objects.filter(user_id=user_id, shopping_list__isnull=True).update(shopping_list_id=default_list.id)
        ShoppingListRecipeSource.objects.filter(user_id=user_id, shopping_list__isnull=True).update(shopping_list_id=default_list.id)


def backwards(apps, schema_editor):
    # Best-effort: just null out references.
    ShoppingListItem = apps.get_model('recipes', 'ShoppingListItem')
    ShoppingListRecipeSource = apps.get_model('recipes', 'ShoppingListRecipeSource')
    ShoppingListItem.objects.update(shopping_list_id=None)
    ShoppingListRecipeSource.objects.update(shopping_list_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0004_shoppinglistrecipesource'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShoppingList',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, verbose_name='Namn')),
                ('is_recurring', models.BooleanField(default=False, verbose_name='Återkommande')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Skapad')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Uppdaterad')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Användare')),
            ],
            options={
                'verbose_name': 'Inköpslista',
                'verbose_name_plural': 'Inköpslistor',
                'ordering': ['-updated_at', '-created_at'],
            },
        ),
        migrations.AddField(
            model_name='shoppinglistitem',
            name='shopping_list',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='items', to='recipes.shoppinglist', verbose_name='Inköpslista'),
        ),
        migrations.AddField(
            model_name='shoppinglistrecipesource',
            name='shopping_list',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sources', to='recipes.shoppinglist', verbose_name='Inköpslista'),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.AlterUniqueTogether(
            name='shoppinglistrecipesource',
            unique_together={('user', 'shopping_list', 'recipe')},
        ),
        migrations.AlterField(
            model_name='shoppinglistitem',
            name='shopping_list',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='recipes.shoppinglist', verbose_name='Inköpslista'),
        ),
        migrations.AlterField(
            model_name='shoppinglistrecipesource',
            name='shopping_list',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sources', to='recipes.shoppinglist', verbose_name='Inköpslista'),
        ),
    ]
