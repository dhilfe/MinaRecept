from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0003_shoppinglistitem'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShoppingListRecipeSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Skapad')),
                ('recipe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='recipes.recipe', verbose_name='Recept')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Användare')),
            ],
            options={
                'verbose_name': 'Inköpslista-källa',
                'verbose_name_plural': 'Inköpslista-källor',
                'unique_together': {('user', 'recipe')},
            },
        ),
    ]
