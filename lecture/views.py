import copy
import os
import zipfile
from ipaddress import ip_network

import dateutil.parser
from django.http import FileResponse

from django.shortcuts import render

from utils.api import APIView, validate_serializer
from utils.cache import cache
from .models import Lecture
from .serializers import (CreateLectureSerializer, EditLectureSerializer, LectureAdminSerializer, LectureSerializer, )

class LectureAPI(APIView):
    @validate_serializer(CreateLectureSerializer)
    def get(self, request):
        lecture_id = request.GET.get("id")
        if lecture_id:
            try:
                lecture = Lecture.objects.get(id=lecture_id)
                ensure_created_by(lecture, request.user)
                return self.success(LectureAdminSerializer(lecture).data)
            except Lecture.DoesNotExist:
                return self.error("강의 없음")

        lectures = Lecture.objects.all()
        if request.user.is_admin():
            lectures = lectures.filter(created_by=request.user)

        keyword = request.GET.get("keyword")
        if keyword:
            lectures = lectures.filter(title__contains=keyword)
        return self.success(self.paginate_data(request, lectures, LectureAdminSerializer))
