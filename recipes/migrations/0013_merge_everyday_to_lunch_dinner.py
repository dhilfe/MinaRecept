from django.db import migrations, models


def forwards(apps, schema_editor):
    Recipe = apps.get_model('recipes', 'Recipe')
    Recipe.objects.filter(dish_type='everyday').update(dish_type='lunch_dinner')


def backwards(apps, schema_editor):
    # Best-effort: map back to everyday.
    Recipe = apps.get_model('recipes', 'Recipe')
    Recipe.objects.filter(dish_type='lunch_dinner').update(dish_type='everyday')


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0012_merge_lunch_and_dinner_to_lunch_dinner'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name='recipe',
            name='dish_type',
            field=models.CharField(
                choices=[
                    ('breakfast', 'Frukost'),
                    ('lunch_dinner', 'Lunch/Middag'),
                    ('appetizer', 'Förrätt'),
                    ('dessert', 'Efterrätt'),
                    ('snack', 'Mellanmål'),
                    ('party', 'Fest'),
                    ('vegetarian', 'Vegetariskt'),
                    ('other', 'Övrigt'),
                ],
                default='lunch_dinner',
                max_length=20,
                verbose_name='Typ av rätt',
            ),
        ),
    ]
