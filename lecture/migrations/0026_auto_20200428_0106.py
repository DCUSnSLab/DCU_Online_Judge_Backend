# Generated by Django 2.1.7 on 2020-04-27 16:06

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lecture', '0025_auto_20200312_1722'),
    ]

    operations = [
        migrations.AlterField(
            model_name='signup_class',
            name='score',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict),
        ),
    ]