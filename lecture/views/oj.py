from django.utils.timezone import now
from utils.shortcuts import datetime2str, check_is_id
from utils.api import APIView

from ..models import Lecture
from ..serializers import LectureSerializer

class LectureAPI(APIView):
    def get(self, request):
        id = request.GET.get("id")
        if not id or not check_is_id(id):
            return self.error("invalid parameter.")
        try:
            lecture = Lecture.objects.get(id=id)
        except Lecture.DoesNotExist:
            return self.error("no lecture exist")
        data = LectureSerializer(lecture).data
        data["now"] = datetime2str(now())
        return self.success(data)

class LectureListAPI(APIView):
    def get(self, request):
        lectures = Lecture.objects.select_related("created_by")
        keyword = request.GET.get("keyword")
        status = request.GET.get("status")
        if keyword:
            lectures = lectures.filter(title__contains=keyword)
		#if status:
		#	cur = now()
		#	if status == LectureStatus.LECTURE_OPEN:
		#		lectures = 
        return self.success(self.paginate_data(request, lectures, LectureSerializer))
