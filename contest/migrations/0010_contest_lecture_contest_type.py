# Generated by Django 2.1.7 on 2020-03-19 04:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contest', '0009_auto_20200224_1209'),
    ]

    operations = [
        migrations.AddField(
            model_name='contest',
            name='lecture_contest_type',
            field=models.TextField(default='실습'),
        ),
    ]