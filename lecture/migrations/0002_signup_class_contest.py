# Generated by Django 2.2.16 on 2020-09-21 16:18

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contest', '0001_initial'),
        ('lecture', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='signup_class',
            name='contest',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='contest.Contest'),
        ),
    ]