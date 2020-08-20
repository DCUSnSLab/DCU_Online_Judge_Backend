from django.utils.datetime_safe import datetime
from django.utils.timezone import now
from django.db.models import Count
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
        yearFilter = data.get("yearFilter")
        semesterFilter = data.get("semesterFilter")

        print("year",sortyear)
        print("subj",sortsubj)
        print("prof",sortprof)
        print("yearfilter",yearFilter)
        print("semesterfilter",semesterFilter)

        if not request.user.is_authenticated:
            return self.error("로그인 후 사용 가능합니다.")

        # print(request.user)
        # print(request.user.is_admin_role())
        # print(request.user.is_super_admin()) 관리자 권한 검사의 경우 해당 함수로 검증하여야 함.

        if request.user.is_super_admin():
            print("관리자입니다.")
            try:
                if sortyear == '1':  #누르면
                    print("sorted")
                    signuplist = signup_class.objects.select_related("lecture").order_by('lecture_id').distinct('lecture_id')
                elif yearFilter != None :
                    print("hey")
                    signuplist = signup_class.objects.select_related("lecture").order_by('lecture_id').distinct('lecture_id')
                    signuplist = signuplist.filter(lecture__year=yearFilter)
                    print(yearFilter)
                elif semesterFilter != None :
                    print("hey")
                    signuplist = signup_class.objects.select_related("lecture").order_by('lecture_id').distinct('lecture_id')
                    signuplist = signuplist.filter(lecture__semester=semesterFilter)
                    print(semesterFilter)
                else: # 값 추출
                    print("normal")
                    signuplist = signup_class.objects.select_related("lecture").order_by('lecture_id').distinct('lecture_id')
                for signup in signuplist:
                    print("Test", signup.lecture.title, signup.lecture.id, signup.lecture.year)
                    signup.isallow = True

                return self.success(self.paginate_data(request, signuplist, SignupClassSerializer))
            except:
                print(self.error())
                return self.error("no lecture exist")

        try:
            signuplist = signup_class.objects.select_related("lecture").order_by("lecture__title")
        except:
            return self.error("no lecture exist")

        signuplist = signuplist.filter(user=request.user.id, lecture__status=True)



        # 한번더 필터 현재월 년도
        # 프론트 콤보박스로 2학기를 보여줌   ///백 - 현재날짜(년도월일) 가져와서 월에따라 학기를 나누고 년도 ///프론트엔드 콤보박스 년도 학기 //
                                # signup.lecture.year
        signuplist = signuplist.filter(lecture__year=2020)
        if (8 >= datetime.today().month >= 3):
            signuplist = signuplist.filter(lecture__semester=1)
            print("1학기");
        else:
            if (datetime.today().month >= 9 or datetime.today().month <= 2):
                signuplist = signuplist.filter(lecture__semester=2)
                print("2학기")

        try:
            if sortyear == '1':  # 누르면
                print("sorted")
                signuplist = signup_class.objects.select_related("lecture").order_by('lecture_id').distinct(
                    'lecture_id')
            elif yearFilter != None:
                print("hey")
                signuplist = signup_class.objects.select_related("lecture").order_by('lecture_id').distinct(
                    'lecture_id')
                signuplist = signuplist.filter(lecture__year=yearFilter)
                print(yearFilter)
            elif semesterFilter != None:
                print("hey")
                signuplist = signup_class.objects.select_related("lecture").order_by('lecture_id').distinct(
                    'lecture_id')
                signuplist = signuplist.filter(lecture__semester=semesterFilter)
                print(semesterFilter)
            else:  # 값 추출
                print("normal")
                signuplist = signup_class.objects.select_related("lecture").order_by('lecture_id').distinct(
                    'lecture_id')
            for signup in signuplist:
                print("Test", signup.lecture.title, signup.lecture.id, signup.lecture.year)
                signup.isallow = True

            return self.success(self.paginate_data(request, signuplist, SignupClassSerializer))
        except:
            print(self.error())
            return self.error("no lecture exist")

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
                print("LID IS NOT NONE user ID", uid, "lid=", lid)
                lec = signup_class.objects.filter(lecture_id=lid, user_id=uid)
            retv = lec
        except signup_class.DoesNotExist:
            retv = None
            print("NOT EXIST", lec)
        return retv