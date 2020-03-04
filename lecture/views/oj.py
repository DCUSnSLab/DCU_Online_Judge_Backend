from django.utils.timezone import now
from utils.shortcuts import datetime2str, check_is_id
from utils.api import APIView

from ..models import Lecture, signup_class
from ..serializers import LectureSerializer, SignupClassSerializer

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
        print("LectureListAPI Called")
        keyword = request.GET.get("keyword")

        try:
            lectures = Lecture.objects.all()
        except:
            return self.error("no lecture exist")

        if keyword:
            lectures = lectures.filter(title__contains=keyword)
            return self.success(self.paginate_data(request, lectures, LectureSerializer))

        signuplist = signup_class.objects.select_related("lecture").order_by("-id")

        signuplist = signuplist.filter(user=request.user.id, lecture__status=True)
        signuplist = signuplist.exclude(isallow=True)

        return self.success(self.paginate_data(request, signuplist, SignupClassSerializer))

class TakingLectureListAPI(APIView):
    def get(self, request):
        print("TakingLectureListAPI Called")
        keyword = request.GET.get("keyword")

        try:
            lectures = Lecture.objects.all()
        except:
            return self.error("no lecture exist")

        if keyword:
            lectures = lectures.filter(title__contains=keyword)
            return self.success(self.paginate_data(request, lectures, LectureSerializer))

        signuplist = signup_class.objects.select_related("lecture").order_by("-id")

        signuplist = signuplist.filter(user=request.user.id, lecture__status=True)
        signuplist = signuplist.exclude(isallow=False)

        return self.success(self.paginate_data(request, signuplist, SignupClassSerializer))

class LectureApplyAPI(APIView):
    def post(self, request):
        print("LectureApplyAPI Called")
        data = request.data
        lecture_id = data.get("lecture_id")
        user_id = data.get("user_id")
        print(data)
        if lecture_id and user_id:
            signup = signup_class.objects.get(lecture=lecture_id, user=user_id)
            print(signup)

        return self.success()

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