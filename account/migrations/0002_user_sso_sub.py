from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="sso_sub",
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
    ]
