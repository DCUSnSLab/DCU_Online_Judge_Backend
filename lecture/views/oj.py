from django.utils.timezone import now
from utils.shortcuts import datetime2str, check_is_id
from utils.api import APIView

from ..models import Lecture, signup_class
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

        print(request.user.id)
        LU = LectureUtil()
        applylist = LU.getSignupList(request.user.id)

        if not (applylist is None):
            for al in applylist:
                print(al.lecture_id, al.user_id)
                #change is apply
                for ll in lectures:
                    if al.lecture_id == ll.id:
                        ll.isapply = True
                        ll.isallow = al.isallow
        else:
            print("None Apply")

		#if status:
		#	cur = now()
		#	if status == LectureStatus.LECTURE_OPEN:
		#		lectures = 
        return self.success(self.paginate_data(request, lectures, LectureSerializer))

class LectureApplyAPI(APIView):
    def post(self, request):
        retv = -1
        data = request.data
        LU = LectureUtil()
        if data.get("lecture_id"):
            if not LU.getSignupList(lid=data.get("lecture_id"), uid=request.user.id):
                appy = signup_class.objects.create(lecture_id=data.get("lecture_id"),
                                                   user_id=request.user.id,
                                                   status=False)
                print("created")
                retv = 1
            else:
                retv = -1

        return self.success(retv)

class LectureUtil:
    def getSignupList(self, uid, lid=None):
        retv = None
        lec = None
        print("LectureUtil lid = ",lid)
        try:
            if lid is None:
                print("LID IS NONE user ID", uid)
                lec = signup_class.objects.filter(user_id=uid)
                print(lec)
            else:
                print("LID IS NOT NONE user ID", uid, "lid=",lid)
                lec = signup_class.objects.filter(lecture_id=lid, user_id=uid)
            retv = lec
        except signup_class.DoesNotExist:
            retv = None
            print("NOT EXIST", lec)
        return retv