# Generated by Django 2.1.7 on 2020-02-20 16:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contest', '0004_remove_contest_assigned_lecture'),
        ('lecture', '0008_auto_20200220_1609'),
    ]

    operations = [
        migrations.CreateModel(
            name='lecture_contest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contest', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contest.Contest')),
                ('lecture', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='lecture.Lecture')),
            ],
        ),
    ]
