# Generated by Django 2.1.7 on 2020-03-11 08:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lecture', '0023_auto_20200311_0051'),
    ]

    operations = [
        migrations.AddField(
            model_name='lecture',
            name='semester',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='lecture',
            name='year',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
    ]