from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0005_shoppinglists'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WeeklyMenu',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, verbose_name='Namn')),
                ('week_number', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Veckonummer')),
                ('year', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='År')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Skapad')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Användare')),
            ],
            options={
                'verbose_name': 'Veckomeny',
                'verbose_name_plural': 'Veckomenyer',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='WeeklyMenuItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.CharField(choices=[('mon', 'Måndag'), ('tue', 'Tisdag'), ('wed', 'Onsdag'), ('thu', 'Torsdag'), ('fri', 'Fredag'), ('sat', 'Lördag'), ('sun', 'Söndag')], max_length=3, verbose_name='Dag')),
                ('menu', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='recipes.weeklymenu', verbose_name='Veckomeny')),
                ('recipe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='recipes.recipe', verbose_name='Recept')),
            ],
            options={
                'verbose_name': 'Veckomeny-rad',
                'verbose_name_plural': 'Veckomeny-rader',
                'unique_together': {('menu', 'day')},
            },
        ),
    ]
