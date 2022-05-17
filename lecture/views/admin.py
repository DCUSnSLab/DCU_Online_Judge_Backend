import copy
import os
import zipfile
from ipaddress import ip_network

import dateutil.parser
from django.http import FileResponse

from account.decorators import ensure_created_by
from problem.models import Problem
from submission.models import Submission
from utils.api import APIView, validate_serializer
from django.db.models import Q, Max

from .LectureAnalysis import lecDispatcher
from .LectureBuilder import UserBuilder
from ..models import Lecture, signup_class, ta_admin_class
from ..serializers import (CreateLectureSerializer, EditLectureSerializer, LectureAdminSerializer, LectureSerializer, TAAdminSerializer, EditTAuserSerializer, PermitTA, )
from account.models import User, AdminType

class LectureAPI(APIView):
    @validate_serializer(CreateLectureSerializer)
    def post(self, request):
        data = request.data
        data["created_by"] = request.user
        lecture = Lecture.objects.create(**data)
        signup_class.objects.create(lecture=lecture, user=request.user, status=False, isallow=True) # 수강 과목 생성 시, 본인이 생성한 수강과목에 대해 별도의 수강신청 없이 접근할 수 있도록
        # lecture_signup_class 테이블에 값을 생성한다.
        return self.success(LectureAdminSerializer(lecture).data)

    #def put(self, request):
    @validate_serializer(EditLectureSerializer)
    def put(self, request):
        data = request.data
        try:
            lecture = Lecture.objects.get(id=data.pop("id"))
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
            print("Try")
            lectures = signup_class.objects.filter(lecture__id=data['lectureID'])
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

        except:
            print("exception")

        return self.success()

    def post(self, request):
        data = request.data

        if data.get("lecture_id") and data.get\
                    ("user_id"):
            appy = signup_class.objects.get(lecture_id=data.get("lecture_id"), user_id=data.get("user_id"))
            #print(appy)
            appy.isallow = True
            appy.save()

            lectures = signup_class.objects.filter(isallow=True, lecture_id=data.get("lecture_id"), user_id=data.get("user_id")).select_related('lecture').order_by('lecture')
            ub = UserBuilder(None) # 사용자 정보 생성 후 lecture_signup_class에 추가하는 부분
            ub.buildLecture(lectures) # 이하동일
            #print("modified")

        return self.success()

    def delete(self, request):
        id = request.GET.get("id")
        lecture_id = request.GET.get("lectureid")
        contest_Id = request.GET.get("contestId")
        if id:
            print("test")
            if lecture_id:
                signup_class.objects.filter(id=id, lecture=lecture_id).delete()
            elif contest_Id:
                signup_class.objects.filter(id=id, contest=contest_Id).delete()
            return self.success()

        return self.error("Invalid Parameter, id is required")

class WaitStudentAddAPI(APIView):
    def post(self, request):
        data = request.data
        print(type(data))
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
                        except:
                            print("no matching user")

        return self.success()