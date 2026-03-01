"""
테스트 데이터 시딩 스크립트
Django shell에서 실행: python manage.py shell < seed_test_data.py
"""
import os
import sys
import random
import uuid
from datetime import datetime, timedelta

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oj.settings')

# Django setup if not already
try:
    django.setup()
except:
    pass

from django.utils import timezone
from account.models import User, UserProfile, AdminType
from lecture.models import Lecture, signup_class
from contest.models import Contest
from problem.models import Problem

# ======== 설정 ========
NUM_STUDENTS = 100
SEMESTERS = [
    {"year": 2025, "semester": 2, "num_lectures": 10},
    {"year": 2026, "semester": 1, "num_lectures": 10},
]
CONTESTS_PER_LECTURE = 5  # 각 과목당 실습 수
STUDENTS_PER_LECTURE = 30  # 각 과목당 수강 학생 수
PROBLEMS_PER_CONTEST = 3  # 각 실습당 문제 수

# 과목명 목록
COURSE_NAMES = [
    "프로그래밍기초", "자료구조", "알고리즘", "운영체제", "데이터베이스",
    "컴퓨터네트워크", "소프트웨어공학", "인공지능", "웹프로그래밍", "모바일프로그래밍",
    "객체지향프로그래밍", "컴퓨터구조", "기계학습", "정보보안", "클라우드컴퓨팅",
    "빅데이터분석", "IoT프로그래밍", "시스템프로그래밍", "컴파일러", "디지털논리설계"
]

# ======== admin 유저 확인 ========
try:
    admin_user = User.objects.filter(admin_type=AdminType.SUPER_ADMIN).first()
    if not admin_user:
        admin_user = User.objects.filter(admin_type=AdminType.ADMIN).first()
    if not admin_user:
        print("ERROR: admin 유저가 없습니다. 먼저 admin 계정을 만들어주세요.")
        sys.exit(1)
    print(f"Admin 유저: {admin_user.username} (id={admin_user.id})")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)


# ======== 1. 학생 100명 생성 ========
print("\n[1/4] 학생 100명 생성 중...")
students = []
for i in range(1, NUM_STUDENTS + 1):
    username = f"test_student_{i:03d}"
    try:
        user = User.objects.get(username=username)
        print(f"  이미 존재: {username}")
    except User.DoesNotExist:
        user = User.objects.create(
            username=username,
            realname=f"테스트학생{i:03d}",
            email=f"student{i:03d}@test.dcu.ac.kr",
            schoolssn=20250000 + i,
            admin_type=AdminType.REGULAR_USER,
        )
        user.set_password("test1234")
        user.save()
        # UserProfile 생성
        UserProfile.objects.get_or_create(
            user=user,
            defaults={"real_name": f"테스트학생{i:03d}"}
        )
    students.append(user)

print(f"  => {len(students)}명 준비 완료")


# ======== 2. 개설과목 20개 생성 ========
print("\n[2/4] 개설과목 생성 중...")
lectures = []
course_idx = 0

for sem_info in SEMESTERS:
    year = sem_info["year"]
    semester = sem_info["semester"]
    num_lec = sem_info["num_lectures"]

    print(f"  {year}년 {semester}학기: {num_lec}개")

    for j in range(num_lec):
        course_name = COURSE_NAMES[course_idx % len(COURSE_NAMES)]
        title = f"[{year}-{semester}] {course_name}"
        course_idx += 1

        # 이미 있는지 확인
        existing = Lecture.objects.filter(title=title, year=year, semester=semester).first()
        if existing:
            print(f"    이미 존재: {title}")
            lectures.append(existing)
            continue

        lecture = Lecture.objects.create(
            title=title,
            description=f"<p>{year}년 {semester}학기 {course_name} 수업입니다.</p>",
            created_by=admin_user,
            year=year,
            semester=semester,
            status=True,
            password="",
            isapply=True,
            isallow=True,
        )
        # 교수(admin)도 수강등록
        signup_class.objects.get_or_create(
            lecture=lecture, user=admin_user,
            defaults={"status": False, "isallow": True}
        )
        lectures.append(lecture)
        print(f"    생성: {title} (id={lecture.id})")

print(f"  => {len(lectures)}개 강의 준비 완료")


# ======== 3. 각 과목당 실습(Contest) + 문제(Problem) 생성 ========
print("\n[3/4] 실습(Contest) 및 문제(Problem) 생성 중...")

for lecture in lectures:
    # 이미 Contest가 있는지 확인
    existing_contests = Contest.objects.filter(lecture=lecture).count()
    if existing_contests >= CONTESTS_PER_LECTURE:
        print(f"  {lecture.title}: 이미 {existing_contests}개 실습 존재, 건너뜀")
        continue

    # 실습 시작 기준일
    if lecture.semester == 1:
        base_date = timezone.make_aware(datetime(lecture.year, 3, 1, 9, 0))
    else:
        base_date = timezone.make_aware(datetime(lecture.year, 9, 1, 9, 0))

    num_to_create = CONTESTS_PER_LECTURE - existing_contests
    for k in range(1, num_to_create + 1):
        contest_title = f"{lecture.title} - 실습{k}"
        start = base_date + timedelta(weeks=k * 2)
        end = start + timedelta(days=7)

        contest = Contest.objects.create(
            title=contest_title,
            description=f"<p>{contest_title} 입니다.</p>",
            real_time_rank=True,
            lecture_contest_type="실습",
            rule_type="ACM",
            start_time=start,
            end_time=end,
            created_by=admin_user,
            visible=True,
            private=False,
            lecture=lecture,
        )

        # 각 실습당 문제 생성
        for p_idx in range(1, PROBLEMS_PER_CONTEST + 1):
            prob_id = f"L{lecture.id}C{contest.id}P{p_idx}"
            Problem.objects.create(
                _id=prob_id,
                contest=contest,
                is_public=False,
                title=f"{contest_title} 문제{p_idx}",
                description=f"<p>문제 {p_idx}번 설명입니다.</p>",
                input_description="<p>입력 설명</p>",
                output_description="<p>출력 설명</p>",
                samples=[{"input": "1", "output": "1"}],
                test_case_id=str(uuid.uuid4()),
                test_case_score=[{"input_name": "1.in", "output_name": "1.out", "score": 100}],
                languages=["C", "C++", "Python3"],
                template={},
                created_by=admin_user,
                time_limit=1000,
                memory_limit=256,
                rule_type="ACM",
                difficulty="Low",
            )

    print(f"  {lecture.title}: {num_to_create}개 실습, 각 {PROBLEMS_PER_CONTEST}개 문제 생성")

print(f"  => 총 실습 수: {Contest.objects.filter(lecture__in=lectures).count()}")


# ======== 4. 수강신청 (각 과목당 30명) ========
print("\n[4/4] 수강신청 등록 중...")
random.seed(42)

for lecture in lectures:
    # 이미 등록된 학생 수 확인 (admin 제외)
    existing_signups = signup_class.objects.filter(
        lecture=lecture
    ).exclude(user=admin_user).count()

    if existing_signups >= STUDENTS_PER_LECTURE:
        print(f"  {lecture.title}: 이미 {existing_signups}명 등록, 건너뜀")
        continue

    # 랜덤하게 30명 선택
    selected = random.sample(students, STUDENTS_PER_LECTURE)
    created_count = 0

    for student in selected:
        _, created = signup_class.objects.get_or_create(
            lecture=lecture, user=student,
            defaults={
                "status": False,
                "isallow": True,
                "realname": student.realname,
                "schoolssn": student.schoolssn,
                "score": {},
            }
        )
        if created:
            created_count += 1

    print(f"  {lecture.title}: {created_count}명 신규 등록")

print(f"  => 총 수강등록 수: {signup_class.objects.filter(lecture__in=lectures).count()}")


# ======== 완료 ========
print("\n===== 테스트 데이터 생성 완료 =====")
print(f"  학생: {len(students)}명")
print(f"  강의: {len(lectures)}개")
print(f"  실습: {Contest.objects.filter(lecture__in=lectures).count()}개")
print(f"  문제: {Problem.objects.filter(contest__lecture__in=lectures).count()}개")
print(f"  수강등록: {signup_class.objects.filter(lecture__in=lectures).count()}건")
