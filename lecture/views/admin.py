import copy
import os
import zipfile
from ipaddress import ip_network

import dateutil.parser
from django.http import FileResponse

from account.decorators import ensure_created_by
from utils.api import APIView, validate_serializer
from utils.cache import cache
from utils.constants import CacheKey
from utils.shortcuts import rand_str
from utils.tasks import delete_files
from .LectureBuilder import UserBuilder
from ..models import Lecture, signup_class
from ..serializers import (CreateLectureSerializer, EditLectureSerializer, LectureAdminSerializer, LectureSerializer, )

from account.models import User

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

        keyword = request.GET.get("keyword")
        if keyword:
            lectures = lectures.filter(title__contains=keyword)
        return self.success(self.paginate_data(request, lectures, LectureAdminSerializer))

    def delete(self, request):
        lecture_id = request.GET.get("id")
        if lecture_id:
            #print("test")
            Lecture.objects.filter(id=lecture_id).delete()
            return self.success()

        return self.error("Invalid Parameter, id is required")

class AdminLectureApplyAPI(APIView):
    def post(self, request):
        data = request.data

        if data.get("lecture_id") and data.get("user_id"):
            appy = signup_class.objects.get(lecture_id=data.get("lecture_id"), user_id=data.get("user_id"))
            #print(appy)
            appy.isallow = True
            appy.save()

            lectures = signup_class.objects.filter(isallow=True, lecture_id=data.get("lecture_id"), user_id=data.get("user_id")).select_related('lecture').order_by('lecture')
            ub = UserBuilder(None)
            ub.buildLecture(lectures)
            #print("modified")

        return self.success()

    def delete(self, request):
        id = request.GET.get("id")
        lecture_id = request.GET.get("lectureid")
        if id:
            print("test")
            signup_class.objects.filter(id=id, lecture=lecture_id).delete()
            return self.success()

        return self.error("Invalid Parameter, id is required")

class WaitStudentAddAPI(APIView):
    def post(self, request):
        data = request.data
        print(type(data))
        lecture_id = data["users"][0][1]
        for user in data["users"]:
            if user[0] != -1:
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