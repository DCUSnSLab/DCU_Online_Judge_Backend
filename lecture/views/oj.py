from django.utils.timezone import now
from utils.shortcuts import datetime2str, check_is_id
from utils.api import APIView

from account.models import User
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

        if not request.user.is_authenticated:
            return self.error("로그인 후 사용 가능합니다.")

        keyword = request.GET.get("keyword")

        try:
            lectures = Lecture.objects.all()
            takinglectures = Lecture.objects.prefetch_related("signup_class_set").exclude(signup_class__user=request.user.id)
            takinglectures = takinglectures.exclude(status=False)
        except:
            return self.error("no lecture exist")

        if keyword:
            lectures = lectures.filter(title__contains=keyword)
            return self.success(self.paginate_data(request, lectures, LectureSerializer))

        '''signuplist = signup_class.objects.select_related("lecture").order_by("-id")

        signuplist = signuplist.filter(user=request.user.id, lecture__status=True)
        signuplist = signuplist.exclude(isallow=True)'''

        lectures = lectures.exclude(status=False)
        lectures = lectures.exclude(created_by=request.user.id)

        for lecture in takinglectures:
            print("taking",lecture.title)

        for lecture in lectures:
            print("all",lecture.title)

        final = lectures & takinglectures

        for lecture in final:
            print(lecture.title)

        # return self.success(self.paginate_data(request, lectures, LectureSerializer))
        return self.success(self.paginate_data(request, final, LectureSerializer))

class TakingLectureListAPI(APIView):
    def get(self, request):
        print("TakingLectureListAPI Called")

        if not request.user.is_authenticated:
            return self.error("로그인 후 사용 가능합니다.")

        keyword = request.GET.get("keyword")

        try:
            signuplist = signup_class.objects.select_related("lecture").order_by("-id")
        except:
            return self.error("no lecture exist")

        signuplist = signuplist.filter(schoolssn=request.user.schoolssn, lecture__status=True)

        for signup in signuplist:
            print(signup.lecture.created_by.realname)

        return self.success(self.paginate_data(request, signuplist, SignupClassSerializer))

class LectureApplyAPI(APIView):
    def post(self, request):
        print("LectureApplyAPI Called")
        data = request.data
        lecture_id = data.get("lecture_id")
        user_id = data.get("user_id")
        realname = data.get("user_realname")
        schoolssn = data.get("user_schoolssn")
        print(data)
        lecture = Lecture.objects.get(id=lecture_id)
        user = User.objects.get(id=user_id)
        try:
            su = signup_class.objects.get(lecture=lecture, realname=realname, schoolssn=schoolssn)
            su.user = user
            su.isallow = True
            su.save()
            return self.success()
        except signup_class.DoesNotExist:
            if lecture_id and user_id:
                signup_class.objects.create(lecture=lecture, user=user, status=False)

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