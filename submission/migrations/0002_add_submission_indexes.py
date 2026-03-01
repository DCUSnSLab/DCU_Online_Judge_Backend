from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('submission', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                # 핵심 인덱스: lecture + user + create_time (재계산 쿼리 최적화)
                'CREATE INDEX IF NOT EXISTS idx_submission_lecture_user_time ON submission (lecture_id, user_id, create_time DESC);',
                # 보조 인덱스: lecture + contest + problem (집계 쿼리 최적화)
                'CREATE INDEX IF NOT EXISTS idx_submission_lecture_contest_problem ON submission (lecture_id, contest_id, problem_id);',
                # 보조 인덱스: lecture + result (ACCEPTED 카운트 최적화)
                'CREATE INDEX IF NOT EXISTS idx_submission_lecture_result ON submission (lecture_id, result);',
            ],
            reverse_sql=[
                'DROP INDEX IF EXISTS idx_submission_lecture_user_time;',
                'DROP INDEX IF EXISTS idx_submission_lecture_contest_problem;',
                'DROP INDEX IF EXISTS idx_submission_lecture_result;',
            ]
        ),
    ]
