# Data migration: Python3 exe_name 갱신
#
# JudgeServer 컨테이너 Python 3.6 → 3.10 업그레이드 시 코드 측
# `_py3_lang_config["compile"]["exe_name"]` 값은 cpython-36.pyc → cpython-310.pyc
# 으로 갱신했으나, SysOptions DB에 박힌 nested config 값은 그대로 남음.
# 이 상태로 채점이 돌면 컴파일 산출물(cpython-310.pyc)과 실행 경로(cpython-36.pyc)가
# 어긋나 Python3 제출이 무음 실패함. 마이그레이션 0003에서 description만 갱신하고
# exe_name을 빠뜨려 추가 마이그레이션으로 보정.

from django.db import migrations


def update_python3_exe_name(apps, schema_editor):
    SysOptions = apps.get_model("options", "SysOptions")

    new_exe_name = "__pycache__/solution.cpython-310.pyc"

    try:
        opt = SysOptions.objects.get(key="languages")
        if isinstance(opt.value, list):
            changed = False
            for lang in opt.value:
                if lang.get("name") != "Python3":
                    continue
                compile_cfg = lang.get("config", {}).get("compile", {})
                if compile_cfg.get("exe_name") != new_exe_name:
                    compile_cfg["exe_name"] = new_exe_name
                    changed = True
            if changed:
                opt.save(update_fields=["value"])
    except SysOptions.DoesNotExist:
        pass


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("options", "0003_update_python3_description"),
    ]

    operations = [
        migrations.RunPython(update_python3_exe_name, noop_reverse),
    ]
