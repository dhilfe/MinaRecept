from django.db import migrations


def forwards(apps, schema_editor):
    Recipe = apps.get_model('recipes', 'Recipe')
    Recipe.objects.filter(dish_type__in=['lunch', 'dinner']).update(dish_type='lunch_dinner')


def backwards(apps, schema_editor):
    Recipe = apps.get_model('recipes', 'Recipe')
    # Best-effort rollback: map merged category back to 'lunch'.
    Recipe.objects.filter(dish_type='lunch_dinner').update(dish_type='lunch')


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0011_weeklyplan_servings'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
