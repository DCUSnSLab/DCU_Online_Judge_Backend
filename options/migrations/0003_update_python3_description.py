# Data migration: Python3 description 갱신
#
# JudgeServer 컨테이너 Python 3.6 → 3.10 업그레이드에 맞춰 코드의
# `_py3_lang_config` description은 "Python 3.5" → "Python 3.10" 으로 갱신했으나,
# SysOptions DB에는 초기화 시점에 박힌 옛 description("Python 3.5")이 남아
# admin UI 툴팁에 그대로 노출됨.

from django.db import migrations


def update_python3_description(apps, schema_editor):
    SysOptions = apps.get_model("options", "SysOptions")

    try:
        opt = SysOptions.objects.get(key="languages")
        if isinstance(opt.value, list):
            changed = False
            for lang in opt.value:
                if lang.get("name") == "Python3" and lang.get("description") != "Python 3.10":
                    lang["description"] = "Python 3.10"
                    changed = True
            if changed:
                opt.save(update_fields=["value"])
    except SysOptions.DoesNotExist:
        pass


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("options", "0002_remove_python2_language"),
    ]

    operations = [
        migrations.RunPython(update_python3_description, noop_reverse),
    ]
