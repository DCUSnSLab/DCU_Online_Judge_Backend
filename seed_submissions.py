"""
제출 내역 테스트 데이터 시딩 스크립트
Django shell에서 실행: python manage.py shell < seed_submissions.py
"""
import os
import sys
import random
from datetime import timedelta

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oj.settings')
try:
    django.setup()
except:
    pass

from django.utils import timezone
from account.models import User
from lecture.models import Lecture, signup_class
from contest.models import Contest
from problem.models import Problem
from submission.models import Submission, JudgeStatus
from utils.shortcuts import rand_str

# ======== 설정 ========
TOTAL_SUBMISSIONS = 1000
TARGET_PREFIX = "[202"  # 시딩된 강의 식별

# 가능한 결과와 비율 (ACCEPTED가 약 50%, 나머지 실패)
RESULT_CHOICES = [
    (JudgeStatus.ACCEPTED, 50),        # 정답 50%
    (JudgeStatus.WRONG_ANSWER, 25),    # 오답 25%
    (JudgeStatus.COMPILE_ERROR, 5),    # 컴파일에러 5%
    (JudgeStatus.CPU_TIME_LIMIT_EXCEEDED, 8),  # 시간초과 8%
    (JudgeStatus.MEMORY_LIMIT_EXCEEDED, 5),    # 메모리초과 5%
    (JudgeStatus.RUNTIME_ERROR, 7),    # 런타임에러 7%
]

LANGUAGES = ["C", "C++", "Python3"]

SAMPLE_CODES = {
    "C": '#include <stdio.h>\nint main() {\n    int a;\n    scanf("%d", &a);\n    printf("%d\\n", a);\n    return 0;\n}',
    "C++": '#include <iostream>\nusing namespace std;\nint main() {\n    int a;\n    cin >> a;\n    cout << a << endl;\n    return 0;\n}',
    "Python3": 'a = int(input())\nprint(a)',
}


def weighted_choice(choices):
    """가중치 기반 랜덤 선택"""
    total = sum(w for _, w in choices)
    r = random.randint(1, total)
    cumulative = 0
    for val, weight in choices:
        cumulative += weight
        if r <= cumulative:
            return val
    return choices[0][0]


def make_statistic_info(result):
    """결과에 따른 statistic_info 생성"""
    if result == JudgeStatus.ACCEPTED:
        return {
            "time_cost": random.randint(10, 500),
            "memory_cost": random.randint(1024, 65536),
            "score": 0,
        }
    elif result == JudgeStatus.COMPILE_ERROR:
        return {
            "time_cost": 0,
            "memory_cost": 0,
            "err_info": "compilation error: expected ';'",
            "score": 0,
        }
    elif result in (JudgeStatus.CPU_TIME_LIMIT_EXCEEDED, JudgeStatus.REAL_TIME_LIMIT_EXCEEDED):
        return {
            "time_cost": 1000,
            "memory_cost": random.randint(1024, 65536),
            "score": 0,
        }
    elif result == JudgeStatus.MEMORY_LIMIT_EXCEEDED:
        return {
            "time_cost": random.randint(10, 500),
            "memory_cost": 262144,
            "score": 0,
        }
    else:
        return {
            "time_cost": random.randint(10, 500),
            "memory_cost": random.randint(1024, 65536),
            "score": 0,
        }


# ======== 데이터 수집 ========
print("제출 내역 시딩 준비 중...")

lectures = list(Lecture.objects.filter(title__startswith=TARGET_PREFIX))
if not lectures:
    print("ERROR: 시딩된 강의를 찾을 수 없습니다.")
    sys.exit(1)

# 각 강의별 등록된 학생과 문제 정보 수집
lecture_data = []
for lec in lectures:
    enrolled = list(
        signup_class.objects.filter(lecture=lec, isallow=True)
        .exclude(user__admin_type__in=["Super Admin", "Admin"])
        .select_related("user")
    )
    problems = list(
        Problem.objects.filter(contest__lecture=lec).select_related("contest")
    )
    if enrolled and problems:
        lecture_data.append({
            "lecture": lec,
            "students": [sc.user for sc in enrolled],
            "problems": problems,
        })

if not lecture_data:
    print("ERROR: 등록된 학생이나 문제를 찾을 수 없습니다.")
    sys.exit(1)

print(f"  강의 {len(lecture_data)}개, 학생/문제 준비 완료")

# ======== 기존 테스트 제출 수 확인 ========
existing_count = Submission.objects.filter(lecture__title__startswith=TARGET_PREFIX).count()
print(f"  기존 제출 수: {existing_count}개")

to_create = max(0, TOTAL_SUBMISSIONS - existing_count)
if to_create == 0:
    print("이미 충분한 제출이 존재합니다.")
    sys.exit(0)

print(f"  {to_create}개 제출 생성 시작...")

# ======== 제출 생성 ========
random.seed(12345)
submissions_to_bulk = []

for i in range(to_create):
    # 랜덤 강의 선택
    ld = random.choice(lecture_data)
    lecture = ld["lecture"]
    student = random.choice(ld["students"])
    problem = random.choice(ld["problems"])
    contest = problem.contest

    # 결과
    result = weighted_choice(RESULT_CHOICES)

    # 언어
    lang = random.choice(LANGUAGES)

    # 제출 시각: 실습 시작 ~ 종료 사이 랜덤
    if contest.start_time and contest.end_time:
        delta = contest.end_time - contest.start_time
        random_offset = timedelta(seconds=random.randint(0, int(delta.total_seconds())))
        submit_time = contest.start_time + random_offset
    else:
        submit_time = timezone.now() - timedelta(days=random.randint(1, 90))

    submissions_to_bulk.append(Submission(
        id=rand_str(),
        contest=contest,
        problem=problem,
        user=student,
        username=student.username,
        code=SAMPLE_CODES.get(lang, SAMPLE_CODES["Python3"]),
        result=result,
        info={},
        language=lang,
        statistic_info=make_statistic_info(result),
        ip="127.0.0.1",
        lecture=lecture,
    ))

    if len(submissions_to_bulk) >= 100:
        Submission.objects.bulk_create(submissions_to_bulk)
        print(f"  {i + 1}/{to_create} 제출 생성됨...")
        submissions_to_bulk = []

# 나머지
if submissions_to_bulk:
    Submission.objects.bulk_create(submissions_to_bulk)

# ======== 결과 확인 ========
total = Submission.objects.filter(lecture__title__startswith=TARGET_PREFIX).count()
accepted = Submission.objects.filter(lecture__title__startswith=TARGET_PREFIX, result=JudgeStatus.ACCEPTED).count()
wrong = Submission.objects.filter(lecture__title__startswith=TARGET_PREFIX, result=JudgeStatus.WRONG_ANSWER).count()
others = total - accepted - wrong

print(f"\n===== 제출 내역 생성 완료 =====")
print(f"  총 제출: {total}개")
print(f"  정답(ACCEPTED): {accepted}개")
print(f"  오답(WRONG_ANSWER): {wrong}개")
print(f"  기타(CE/TLE/MLE/RE): {others}개")
