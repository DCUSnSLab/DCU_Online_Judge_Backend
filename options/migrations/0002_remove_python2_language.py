# Data migration: Python 2 채점 지원 제거 후속 정리
#
# JudgeServer 컨테이너의 Ubuntu 22.04 업그레이드로 Python 2 패키지가
# 빠지면서 코드 측 흔적은 제거됐으나, 기존 운영 DB에는 옛 default 값이
# 그대로 박혀 있어 admin UI에서 Python2가 계속 노출됨.
#
# 정리 대상:
#   1) SysOptions.languages — 시스템 전역 가용 언어 목록 (dict 리스트)
#   2) Problem.languages    — 각 문제의 허용 언어 목록 (string 리스트)

from django.db import migrations


def remove_python2(apps, schema_editor):
    SysOptions = apps.get_model("options", "SysOptions")
    Problem = apps.get_model("problem", "Problem")

    try:
        opt = SysOptions.objects.get(key="languages")
        if isinstance(opt.value, list):
            cleaned = [lang for lang in opt.value if lang.get("name") != "Python2"]
            if cleaned != opt.value:
                opt.value = cleaned
                opt.save(update_fields=["value"])
    except SysOptions.DoesNotExist:
        pass

    for problem in Problem.objects.all():
        langs = problem.languages or []
        if "Python2" in langs:
            problem.languages = [lang for lang in langs if lang != "Python2"]
            problem.save(update_fields=["languages"])


def noop_reverse(apps, schema_editor):
    # Python 2 자체가 채점 환경에서 제거됐으므로 되돌릴 의미가 없음.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("options", "0001_initial"),
        ("problem", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(remove_python2, noop_reverse),
    ]
