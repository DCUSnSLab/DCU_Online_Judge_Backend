from django.utils.timezone import now
from django.db.models import Count
from utils.shortcuts import datetime2str, check_is_id
from utils.api import APIView

from account.models import User
from ..models import Lecture, signup_class, ta_admin_class
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

        if request.user.is_super_admin(): # 관리자 계정의 개설 과목 출력
            print("관리자입니다.")
            try:
                lectures = Lecture.objects.all().order_by("title")
                return self.success(self.paginate_data(request, lectures, LectureSerializer))
            except:
                return self.error("no lecture exist")

        keyword = request.GET.get("keyword")

        try:
            lectures = Lecture.objects.prefetch_related("signup_class_set__user").order_by('title').exclude(signup_class__user=request.user)
        except:
            return self.error("no lecture exist")

        if keyword:
            lectures = lectures.filter(title__contains=keyword)
            return self.success(self.paginate_data(request, lectures, LectureSerializer))

        # return self.success(self.paginate_data(request, lectures, LectureSerializer))
        return self.success(self.paginate_data(request, lectures, LectureSerializer))

class TakingLectureListAPI(APIView): # 수강중인 과목 목록
    def get(self, request):
        print("TakingLectureListAPI Called")
        data = request.data

        sortyear = data.get("yearSort")
        sortsubj = data.get("subjSort")
        sortprof = data.get("profSort")

        print("year",sortyear)
        print("subj",sortsubj)
        print("prof",sortprof)

        if not request.user.is_authenticated:
            return self.error("로그인 후 사용 가능합니다.")

        # print(request.user)
        # print(request.user.is_admin_role())
        # print(request.user.is_super_admin()) 관리자 권한 검사의 경우 해당 함수로 검증하여야 함.

        if request.user.is_super_admin():
            print("관리자입니다.")
            try:
                if sortyear == '1':
                    print("sorted")
                    signuplist = signup_class.objects.select_related("lecture").order_by('lecture_id').distinct('lecture_id')
                else:
                    print("normal")
                    signuplist = signup_class.objects.select_related("lecture").order_by('lecture_id').distinct('lecture_id')
                for signup in signuplist:
                    #print("Test ",signup.lecture.title, signup.lecture.id, signup.lecture.year)
                    signup.isallow = True

                return self.success(self.paginate_data(request, signuplist, SignupClassSerializer))
            except:
                print(self.error())
                return self.error("no lecture exist")

        try:
            signuplist = signup_class.objects.all()

        except:
            return self.error("no lecture exist")

        if request.user.is_semi_admin():
            TAUserLecList = ta_admin_class.objects.filter(user=request.user.id).select_related("lecture").order_by("lecture__title")
            TALec = ''
            for lec in TAUserLecList:
                if TALec == '':
                    TALec = signuplist.filter(lecture__id=lec.lecture_id).order_by('lecture_id').distinct('lecture_id')
                else:
                    TALec = TALec.union(signuplist.filter(lecture__id=lec.lecture_id).order_by('lecture_id').distinct('lecture_id'))

            #test = signuplist.filter(lecture=test.lecture)
            signuplist = TALec
        else:
            signuplist = signuplist.filter(user=request.user.id, lecture__status=True)

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
                signup_class.objects.create(lecture=lecture, user=user, realname=realname, schoolssn=schoolssn, status=False)

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