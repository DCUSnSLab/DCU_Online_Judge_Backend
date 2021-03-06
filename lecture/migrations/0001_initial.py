# Generated by Django 2.2.16 on 2020-09-21 15:30

from django.conf import settings
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import utils.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Lecture',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.TextField()),
                ('description', utils.models.RichTextField()),
                ('year', models.IntegerField()),
                ('semester', models.IntegerField()),
                ('status', models.BooleanField()),
                ('password', models.TextField()),
                ('isapply', models.BooleanField(default=False)),
                ('isallow', models.BooleanField(default=False)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'lecture',
            },
        ),
        migrations.CreateModel(
            name='ta_admin_class',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('realname', models.TextField(default=None, null=True)),
                ('schoolssn', models.IntegerField(default=None, null=True)),
                ('lecture_isallow', models.BooleanField(default=False)),
                ('code_isallow', models.BooleanField(default=False)),
                ('score_isallow', models.BooleanField(default=False)),
                ('lecture', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='lecture.Lecture')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='signup_class',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.BooleanField(default=False)),
                ('isallow', models.BooleanField(default=False)),
                ('realname', models.TextField(default=None, null=True)),
                ('schoolssn', models.IntegerField(default=None, null=True)),
                ('score', django.contrib.postgres.fields.jsonb.JSONField(default=dict)),
                ('etc', models.TextField(null=True)),
                ('lecture', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='lecture.Lecture')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
