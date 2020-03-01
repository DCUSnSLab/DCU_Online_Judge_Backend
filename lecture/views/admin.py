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
from ..models import Lecture, signup_class
from ..serializers import (CreateLectureSerializer, EditLectureSerializer, LectureAdminSerializer, LectureSerializer, )

class LectureAPI(APIView):
    @validate_serializer(CreateLectureSerializer)
    def post(self, request):
        data = request.data
        data["created_by"] = request.user
        lecture = Lecture.objects.create(**data)
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



class AdminLectureApplyAPI(APIView):
    def post(self, request):
        data = request.data

        if data.get("lecture_id") and data.get("user_id"):
            appy = signup_class.objects.get(lecture_id=data.get("lecture_id"), user_id=data.get("user_id"))
            print(appy)
            appy.isallow = True
            appy.save()
            print("modified")

        return self.success()

    def delete(self, request):
        user_id = request.GET.get("id")
        print(user_id)
        if user_id:
            print("test")
            signup_class.objects.filter(user_id=user_id).delete()
            return self.success()

        return self.error("Invalid Parameter, id is required")