import copy
import os
import zipfile
from ipaddress import ip_network

import dateutil.parser
from django.http import FileResponse

from account.decorators import ensure_created_by, super_admin_required
from problem.models import Problem
from submission.models import Submission
from utils.api import APIView, validate_serializer
from django.db.models import Q, Max

from .LectureAnalysis import lecDispatcher
from .LectureBuilder import UserBuilder
from contest.models import Contest, ContestUser
from ..models import Lecture, signup_class, ta_admin_class
from ..serializers import (CreateLectureSerializer, EditLectureSerializer, LectureAdminSerializer, LectureSerializer, TAAdminSerializer, EditTAuserSerializer, PermitTA, )
from account.models import User, AdminType

class LectureAPI(APIView):
    @validate_serializer(CreateLectureSerializer)
    def post(self, request):
        data = request.data
        proxy_created_by = data.pop("created_by_id")
        if proxy_created_by is not None: # created_by_id가 요청을 한 사용자가 아닌 별도로 명시된 사용자인 경우
            proxy_user = User.objects.get(id=proxy_created_by)
            data["created_by"] = proxy_user
            lecture = Lecture.objects.create(**data)
            signup_class.objects.create(lecture=lecture, user=proxy_user, status=False,
                                        isallow=True)  # 수강 과목 생성 시, 본인이 생성한 수강과목에 대해 별도의 수강신청 없이 접근할 수 있도록
        else:
            data["created_by"] = request.user
            lecture = Lecture.objects.create(**data)
            signup_class.objects.create(lecture=lecture, user=request.user, status=False, isallow=True) # 수강 과목 생성 시, 본인이 생성한 수강과목에 대해 별도의 수강신청 없이 접근할 수 있도록
        # lecture_signup_class 테이블에 값을 생성한다.
        return self.success(LectureAdminSerializer(lecture).data)

    #def put(self, request):
    @validate_serializer(EditLectureSerializer)
    def put(self, request):
        data = request.data
        lecture_id = data.pop("id")
        proxy_created_by = data.pop("created_by_id")
        try:
            lecture = Lecture.objects.get(id=lecture_id)
            if proxy_created_by is not None:  # created_by_id가 요청을 한 사용자가 아닌 별도로 명시된 사용자인 경우
                proxy_user = User.objects.get(id=proxy_created_by)
                lecture.created_by = proxy_user
                print("proxy")

                print(proxy_created_by)
                contests = Contest.objects.all().filter(lecture=lecture_id)
                for contest in contests:
                    contest.created_by = proxy_user
                    contest.save()
            ensure_created_by(lecture, request.user)
        except Lecture.DoesNotExist:
            return self.error("no lecture exist")

        for k, v in data.items():
            setattr(lecture, k, v)
        lecture.save()
        return self.success(LectureAdminSerializer(lecture).data)

    def get(self, request):
        lecture_id = request.GET.get("id")

        if lecture_id:
            try:
                lecture = Lecture.objects.get(id=lecture_id)
                ensure_created_by(lecture, request.user)
                return self.success(LectureAdminSerializer(lecture).data)
            except Lecture.DoesNotExist:
                return self.error("no lecture exist")

        lectures = Lecture.objects.all().order_by("-id")
        if request.user.is_admin():
            lectures = lectures.filter(created_by=request.user)
        elif request.user.is_semi_admin(): # 수정필요
            tauser = ta_admin_class.objects.filter(user=request.user)
            tauser_lec = ''
            for lec_list in tauser:
                extract_lec = lectures.filter(id=lec_list.lecture.id)
                if tauser_lec == '' and (lec_list.lecture_isallow or lec_list.score_isallow):
                    tauser_lec = extract_lec
                elif tauser_lec != '' and (lec_list.lecture_isallow or lec_list.score_isallow):
                    tauser_lec = tauser_lec.union(extract_lec)
            lectures = tauser_lec

        keyword = request.GET.get("keyword")

        if keyword:
            lectures = lectures.filter(title__contains=keyword)

        if lectures == '':
            return self.success()
        else:
            return self.success(self.paginate_data(request, lectures, LectureAdminSerializer))

    def delete(self, request):
        lecture_id = request.GET.get("id")
        if lecture_id:
            #print("test")
            Lecture.objects.filter(id=lecture_id).delete()
            return self.success()

        return self.error("Invalid Parameter, id is required")

class TAAdminLectureAPI(APIView):
    def put(self, request):
        permit = request.GET.getlist("permit[]")
        ssn = request.GET.get("ssn")
        lecture_id = request.GET.get("lecture_id")

        # TA User permit migrate
        ta_update = ta_admin_class.objects.get(lecture__id=lecture_id, schoolssn=ssn)

        ta_update.code_isallow = PermitTA.CODE in permit and True or False
        ta_update.lecture_isallow = PermitTA.PROBLEM in permit and True or False
        ta_update.score_isallow = PermitTA.SCORE in permit and True or False

        ta_update.save()

        return self.success()

    def get(self,  request):
        lecture_id = request.GET.get("lecture_id")
        if request.user.is_admin() or request.user.is_super_admin():
            lecture = Lecture.objects.get(id=lecture_id)
            ta_list = ta_admin_class.objects.filter(lecture=lecture)
            return self.success(self.paginate_data(request, ta_list, TAAdminSerializer))
        return self.success()

    def post(self, request):
        data = request.data
        print("name")
        print(data.get("Name"))
        if data.get("add"):
            user = User.objects.get(id=data.get("User"))
            if user.admin_type == AdminType.ADMIN:
                return self.error("관리자 계정입니다. 다시 확인 해주세요.")
            lecture = Lecture.objects.get(id=data.get("lecture_id"))
            if ta_admin_class.objects.filter(Q(user=user, lecture=lecture)).exists() is False:
                addTAUser = ta_admin_class.objects.create(lecture=lecture, user=user, realname=user.realname, schoolssn=user.schoolssn)
                user.admin_type = AdminType.TA_ADMIN
                user.save()
                return self.success(TAAdminSerializer(addTAUser).data)

        #DataType
        try:
            if data.get("searchType") == '이름':
                user = User.objects.filter(realname=data.get("Name"))
            else:
                user = User.objects.filter(schoolssn=data.get("Name"))
        except User.DoesNotExist:
            return self.error("조회 실패. 다시 확인 해주세요.")
        #쿼리 조회후 해당하는 유저가 있을 경우 해당 반환 값 반환
        if user.exists():
            lecture = Lecture.objects.get(id=data.get("lecture_id"))
            if ta_admin_class.objects.filter(Q(realname=data.get("Name"), lecture=lecture)).exists() is False:
                from account.serializers import UserSerializer
                return self.success(self.paginate_data(request, user, UserSerializer))
            else:
                return self.error("중복된 학생입니다. 다시 확인 해주세요.")
        else:
            return self.error("조회 실패. 다시 확인 해주세요.")

    def delete(self, request):
        ssn = request.data.get("ssn")
        lecture_id = request.data.get("lecture_id")
        if ssn:
            delete_user = ta_admin_class.objects.filter(schoolssn=ssn)
            user = User.objects.get(id=delete_user[0].user.id)
            if delete_user.count() == 1:
                user.admin_type = AdminType.REGULAR_USER
                user.save()
            else:
                delete_user = delete_user.filter(lecture__id=lecture_id)
            delete_user.delete()
            return self.success()
        else:
            return self.error("학번을 조회 실패. 학번을 확인 해주세요.")


class AdminLectureApplyAPI(APIView):
    def put(self, request):
        data = request.data
        try:
            print("Try asdfljkawsjdlaiwjxeglawsdjg")
            lectures = signup_class.objects.filter(lecture__id=data['lectureId'])
            lid = -1
            total = lectures.count()
            cnt = 0
            for lec in lectures:
                cnt += 1

                if not lec.isallow:
                    continue

                if lec.user.admin_type == AdminType.SUPER_ADMIN or lec.user.admin_type == AdminType.ADMIN:
                    continue

                if lid != lec.lecture_id:
                    lid = lec.lecture_id

                    plist = Problem.objects.filter(contest__lecture=lec.lecture_id).prefetch_related('contest')

                    # test
                    LectureInfo = lecDispatcher()
                    for p in plist:
                        LectureInfo.migrateProblem(p)

                    # get Submission
                    sublist = Submission.objects.filter(lecture=lec.lecture_id)

                ldates = sublist.filter(user=lec.user).values('contest', 'problem').annotate(
                    latest_created_at=Max('create_time'))
                sdata = sublist.filter(create_time__in=ldates.values('latest_created_at')).order_by('-create_time')
                LectureInfo.cleanDataForScorebard()

                for submit in sdata:
                    LectureInfo.associateSubmission(submit)

                lec.score = LectureInfo.toDict()
                lec.save()

                print("(", cnt, "/", total, ")", lec.lecture_id, lec.id, lec.user.realname, lec.user.username,
                      lec.lecture.title, 'Completedd')

        except Exception as e:
            print("exception")
            print(traceback.format_exc())

        return self.success()

    def post(self, request):
        data = request.data

        if data.get("lecture_id") and data.get("user_id"):
            appy = signup_class.objects.get(lecture_id=data.get("lecture_id"), user_id=data.get("user_id"))
            #print(appy)
            appy.isallow = True
            appy.save()

            lectures = signup_class.objects.filter(isallow=True, lecture_id=data.get("lecture_id"), user_id=data.get("user_id")).select_related('lecture').order_by('lecture')
            ub = UserBuilder(None) # 사용자 정보 생성 후 lecture_signup_class에 추가하는 부분
            ub.buildLecture(lectures) # 이하동일
            #print("modified")

            contests = Contest.objects.filter(lecture_id=data.get("lecture_id"), lecture_contest_type="대회")
            #if contests.exists():
            #    for contest in contests:
            #        ContestUser.objects.create(contest_id=contest.id, user_id=data.get("user_id"), start_time=None, end_time=None)

        return self.success()

    def delete(self, request):
        id = request.GET.get("id")
        lecture_id = request.GET.get("lectureid")
        contest_Id = request.GET.get("contestId")
        if id:
            print("test")
            if lecture_id:
                # 과목 삭제 시, ContestUser 내 해당 과목의 대회와 관련된 행 삭제 (working)
                # sc = signup_class.objects.get(id=id, contest=contest_Id)
                # user_id = sc.user_id
                signup_class.objects.filter(id=id, lecture=lecture_id).delete()
            elif contest_Id:
                sc = signup_class.objects.get(id=id, contest=contest_Id)
                user_id = sc.user_id
                ContestUser.objects.filter(user_id=user_id, contest_id=contest_Id).delete()
                signup_class.objects.filter(id=id, contest=contest_Id).delete()
            return self.success()

        return self.error("Invalid Parameter, id is required")

class WaitStudentAddAPI(APIView):
    def post(self, request):
        data = request.data
        if data["users"][0][0] == 'contestId':
            print('contest signup')
            lecture_id = data["users"][0][1]
            for user in data["users"]:
                if user[0] != 'contestId' and user[0] != 'lectureId':
                    print(user[0])
                    print(user[1])
                    try:  # 이미 수강신청한 사용자가 있는지 확인하고, 있는 경우 isallow를 true로 변경한다.
                        user = signup_class.objects.get(contest_id=lecture_id, realname=user[1], schoolssn=user[0])
                        if user.user_id is None:  # 이미 있다고 하더라고 실제 사용자 id가 없으면 건너뛴다.
                            continue
                        else:
                            user.isallow = True  # 해당 사용자의 isallow 값을 True로 변경하고 저장한다.
                            user.save()
                    except:
                        signup_class.objects.create(contest_id=lecture_id, user_id=None, isallow=False,
                                                    realname=user[1], schoolssn=user[0])
                        try:  # 기존 회원가입한 사용자 중, 등록한 학번과 동일한 학번을 가진 사용자를 가져온다.
                            user = User.objects.get(realname=user[1], schoolssn=user[0])
                            signuplist = signup_class.objects.filter(schoolssn=user.schoolssn, contest_id=lecture_id)
                            for signup in signuplist:
                                signup.user = user
                                signup.isallow = True
                                signup.save()
                            # if not ContestUser.objects.filter(contest_id=lecture_id, user_id=user.id):
                            #    ContestUser.objects.create(contest_id=lecture_id, user_id=user.id, start_time=None, end_time=None)
                            ub = UserBuilder(None)
                            ub.buildLecture(signup.select_related('contest').order_by('contest'))
                        except:
                            print("no matching user")

        elif data["users"][0][0] == 'lectureId':
            print('lecture signup')
            lecture_id = data["users"][0][1]
            for user in data["users"]:
                if user[0] != 'contestId' and user[0] != 'lectureId':
                    print(user[0])
                    print(user[1])
                    try: # 이미 수강신청한 사용자가 있는지 확인하고, 있는 경우 isallow를 true로 변경한다.
                        user = signup_class.objects.get(lecture_id=lecture_id, realname=user[1], schoolssn=user[0])
                        if user.user_id is None: # 이미 있다고 하더라고 실제 사용자 id가 없으면 건너뛴다.
                            continue
                        else:
                            user.isallow = True # 해당 사용자의 isallow 값을 True로 변경하고 저장한다.
                            user.save()
                    except:
                        signup_class.objects.create(lecture_id=lecture_id, user_id=None, isallow=False, realname=user[1], schoolssn=user[0])

                        try:# 기존 회원가입한 사용자 중, 등록한 학번과 동일한 학번을 가진 사용자를 가져온다.
                            user = User.objects.get(realname=user[1], schoolssn=user[0])
                            signuplist = signup_class.objects.filter(schoolssn=user.schoolssn, lecture_id=lecture_id)
                            for signup in signuplist:
                                signup.user = user
                                signup.isallow = True
                                signup.save()

                            ub = UserBuilder(None)
                            ub.buildLecture(signup.select_related('lecture').order_by('lecture'))
                            # ContestUser.objects.create(contest_id=data["users"][0][0], user_id=user.id, start_time=None,
                            #                            end_time=None)
                        except:
                            print("no matching user")

        return self.success()


class BatchMigrateAPI(APIView):
    """년도/학기 조건으로 해당하는 모든 강의의 수강생 성적을 일괄 재계산"""
    @super_admin_required
    def get(self, request):
        """[최적화] Django annotation으로 N×6 쿼리를 최소화"""
        from django.db.models import Count, Subquery, OuterRef, IntegerField
        from django.db.models.functions import Coalesce

        year = request.GET.get("year")
        semester = request.GET.get("semester")

        if not year or not semester:
            return self.error("year and semester are required")

        target_lectures = Lecture.objects.filter(year=year, semester=semester).select_related('created_by')
        if not target_lectures.exists():
            return self.success({"lectures": [], "summary": {}})

        # 전체 lecture_ids
        lecture_ids = list(target_lectures.values_list('id', flat=True))

        # 1. 일괄 집계: signup_class (학생 수)
        from collections import defaultdict
        student_counts = defaultdict(int)
        scored_counts = defaultdict(int)
        for sc in signup_class.objects.filter(
            lecture_id__in=lecture_ids, isallow=True
        ).exclude(
            user__admin_type__in=[AdminType.SUPER_ADMIN, AdminType.ADMIN]
        ).values('lecture_id', 'score'):
            student_counts[sc['lecture_id']] += 1
            if sc['score'] and sc['score'] != {}:
                scored_counts[sc['lecture_id']] += 1

        # 2. 일괄 집계: Contest 수 (타입별)
        contest_stats = defaultdict(lambda: {'total': 0, '실습': 0, '과제': 0, '대회': 0})
        for c in Contest.objects.filter(lecture_id__in=lecture_ids).values('lecture_id', 'lecture_contest_type'):
            lid = c['lecture_id']
            contest_stats[lid]['total'] += 1
            ctype = c['lecture_contest_type']
            if ctype in contest_stats[lid]:
                contest_stats[lid][ctype] += 1

        # 3. 일괄 집계: Problem 수
        problem_counts = defaultdict(int)
        for p in Problem.objects.filter(
            contest__lecture_id__in=lecture_ids
        ).values('contest__lecture_id').annotate(cnt=Count('id')):
            problem_counts[p['contest__lecture_id']] = p['cnt']

        # 4. 일괄 집계: Submission 수 + ACCEPTED 수
        submission_stats = defaultdict(lambda: {'total': 0, 'accepted': 0})
        for s in Submission.objects.filter(
            lecture_id__in=lecture_ids
        ).values('lecture_id').annotate(
            total=Count('id'),
            accepted=Count('id', filter=Q(result=0))
        ):
            submission_stats[s['lecture_id']] = {
                'total': s['total'],
                'accepted': s['accepted']
            }

        # 결과 조합
        lectures_info = []
        total_students = 0
        total_contests = 0
        total_problems = 0
        total_submissions = 0

        for lecture in target_lectures:
            lid = lecture.id
            student_count = student_counts[lid]
            cs = contest_stats[lid]
            pc = problem_counts[lid]
            ss = submission_stats[lid]

            lectures_info.append({
                "id": lid,
                "title": lecture.title,
                "created_by": lecture.created_by.realname or lecture.created_by.username,
                "student_count": student_count,
                "training_count": cs['실습'],
                "assignment_count": cs['과제'],
                "exam_count": cs['대회'],
                "contest_count": cs['total'],
                "problem_count": pc,
                "submission_count": ss['total'],
                "accepted_count": ss['accepted'],
                "scored_students": scored_counts[lid],
                "status": lecture.status,
            })

            total_students += student_count
            total_contests += cs['total']
            total_problems += pc
            total_submissions += ss['total']

        return self.success({
            "lectures": lectures_info,
            "summary": {
                "total_lectures": len(lectures_info),
                "total_students": total_students,
                "total_contests": total_contests,
                "total_problems": total_problems,
                "total_submissions": total_submissions,
            }
        })

    @super_admin_required
    def put(self, request):
        """[메모리 최적화] DB GROUP BY 집계로 최신 제출만 가져오기 (OOMKilled 방지)"""
        import time as _time
        import gc
        from collections import defaultdict

        data = request.data
        lecture_id = data.get("lecture_id")

        if not lecture_id:
            return self.error("lecture_id is required")

        try:
            lecture = Lecture.objects.get(id=lecture_id)
        except Lecture.DoesNotExist:
            return self.error(f"강의 ID {lecture_id}를 찾을 수 없습니다.")

        t_start = _time.time()
        lecture_student_count = 0

        try:
            # ── 1. 수강생 목록 (admin 제외) ──
            signups = list(
                signup_class.objects.filter(lecture=lecture, isallow=True)
                .select_related('user')
                .exclude(user__admin_type__in=[AdminType.SUPER_ADMIN, AdminType.ADMIN])
            )
            if not signups:
                return self.success({
                    "lecture_id": lecture.id, "title": lecture.title,
                    "student_count": 0, "elapsed_ms": 0
                })

            student_user_ids = {s.user_id for s in signups}

            # ── 2. 문제 목록 & LectureInfo 구조 구성 (1회) ──
            plist = Problem.objects.filter(
                contest__lecture=lecture
            ).select_related('contest')

            LectureInfo = lecDispatcher()
            for p in plist:
                LectureInfo.migrateProblem(p)

            # ── 3. [메모리 최적화] DB에서 (user, contest, problem)별 최신 제출 ID만 집계 ──
            # 기존: list(Submission.objects.filter(lecture=lecture)) → 30만건 전체 메모리 로딩 (OOMKilled 원인)
            # 변경: DB GROUP BY로 최신 ID만 가져옴 → ~5천건만 메모리 로딩
            latest_sub_ids = list(
                Submission.objects.filter(
                    lecture=lecture,
                    user_id__in=student_user_ids
                )
                .values('user_id', 'contest_id', 'problem_id')
                .annotate(latest_id=Max('id'))
                .values_list('latest_id', flat=True)
            )

            # ── 4. 최신 제출만 가져와서 user별 그룹핑 ──
            user_latest_subs = defaultdict(list)
            for sub in Submission.objects.filter(
                id__in=latest_sub_ids
            ).select_related('contest', 'problem').defer('code').iterator():
                user_latest_subs[sub.user_id].append(sub)

            total_latest_count = len(latest_sub_ids)
            del latest_sub_ids  # 메모리 해제

            # ── 5. 학생별 성적 계산 (DB 쿼리 없음, 순수 Python) ──
            updated_signups = []
            for signup in signups:
                uid = signup.user_id
                subs = user_latest_subs.get(uid, [])

                LectureInfo.cleanDataForScorebard()
                for sub in subs:
                    LectureInfo.associateSubmission(sub)

                signup.score = copy.deepcopy(LectureInfo.toDict())
                updated_signups.append(signup)
                lecture_student_count += 1

            # ── 6. Bulk Save (1회 DB write) ──
            if updated_signups:
                signup_class.objects.bulk_update(updated_signups, ['score'], batch_size=50)

            elapsed_ms = int((_time.time() - t_start) * 1000)
            print(f"[BatchMigrate] Lecture '{lecture.title}' (id={lecture.id}) "
                  f"- {lecture_student_count} students, {total_latest_count} latest subs (memory-optimized), {elapsed_ms}ms")

            # ── 7. 메모리 정리 (gunicorn 워커 재사용 대비) ──
            del user_latest_subs, updated_signups, signups
            gc.collect()

            return self.success({
                "lecture_id": lecture.id,
                "title": lecture.title,
                "student_count": lecture_student_count,
                "elapsed_ms": elapsed_ms
            })

        except Exception as e:
            import traceback
            print(f"[BatchMigrate] Error in lecture '{lecture.title}' (id={lecture.id})")
            print(traceback.format_exc())
            gc.collect()
            return self.success({
                "lecture_id": lecture.id,
                "title": lecture.title,
                "student_count": lecture_student_count,
                "error": str(e)
            })

