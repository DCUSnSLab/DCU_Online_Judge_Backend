from django.utils.timezone import now
from django.db.models import Count

from contest.models import Contest
from utils.shortcuts import datetime2str, check_is_id
from utils.api import APIView

from account.models import User
from contest.models import ContestUser
from ..models import Lecture, signup_class, ta_admin_class
from ..serializers import LectureSerializer, SignupClassSerializer
from problem.serializers import ContestExitSerializer

class LectureAPI(APIView):
    def post(self, request):
        data = request.data
        contestID = data.get("contestID")
        if contestID:
            lecture = Contest.objects.get(id=contestID)
            lecture = lecture.lecture.id
            return self.success(lecture)
        return self.error()

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

class ContestExitInfoListAPI(APIView):  # 수강 과목 내 학생 목록에서 시험 퇴실 여부 값 조회 목적
    def get(self, request):
        print("ContestExitInfoListAPI called")
        contest_id = request.GET.get("contest_id")
        user_id = request.GET.get("user_id")
        if not contest_id:
            return self.error("Invalid parameter, contest_id is required")
        try:
            CU = ContestUser.objects.get(contest_id=contest_id, user_id=user_id)
            if CU:
                return self.success(ContestExitSerializer(CU).data)
            else:
                return self.success()
        except:
            return self.error("Contest %s doesn't exist" % user.id)


class CheckingAIhelperFlagAPI (APIView):
    def post(self, request):
        data = request.data
        contestID = data.get("contestID")
        if contestID:
            lecture = Contest.objects.get(id=contestID)
            lecture = lecture.lecture.id
            aihelperflag = Lecture.objects.get(id=lecture)
            aihelperflag = aihelperflag.aihelper_status
            return self.success(aihelperflag)
        return self.error()

class LectureListAPI(APIView):
    def get(self, request):
        print("LectureListAPI Called")
        print("LectureListAPI Called 2")
        from datetime import datetime
        year = datetime.today().year
        semester = (8>datetime.today().month>=3) and 1 or ((3>datetime.today().month>=1) and 3 or 2)

        if not request.user.is_authenticated:
            return self.error("로그인 후 사용 가능합니다.")

        if request.user.is_super_admin(): # 관리자 계정의 개설 과목 출력
            print("관리자입니다.")
            try:
                lectures = Lecture.objects.filter(year=year, semester=semester).order_by("title")
                return self.success(self.paginate_data(request, lectures, LectureSerializer))
            except:
                return self.error("no lecture exist")

        keyword = request.GET.get("keyword")

        try:
            lectures = Lecture.objects.filter(year=year, semester=semester, status=True).prefetch_related("signup_class_set__user").order_by('title').exclude(signup_class__user=request.user)
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
                signuplist = signup_class.objects.select_related("lecture").filter(lecture__year=str(sortyear), lecture__semester=str(sortsubj)).order_by('lecture_id').distinct('lecture_id')
                for signup in signuplist:
                    signup.isallow = True

                return self.success(self.paginate_data(request, signuplist, SignupClassSerializer))
            except:
                print(self.error())
                return self.error("no lecture exist!!")     # error !!

        try:
            # signuplist = signup_class.objects.all()
            signuplist = signup_class.objects.select_related("lecture").filter(lecture__year=str(sortyear), lecture__semester=str(sortsubj))

        except:
            return self.error("no lecture exist")

        if request.user.is_semi_admin():
            TAUserLecList = ta_admin_class.objects.select_related("user").filter(user=request.user.id)
            TALec = ''
            for lec in TAUserLecList:
                if TALec == '':
                    TALec = signuplist.filter(lecture__id=lec.lecture_id).order_by('lecture_id').distinct('lecture_id')
                else:
                    TALec = TALec.union(signuplist.filter(lecture__id=lec.lecture_id).order_by('lecture_id').distinct('lecture_id'))

        elif request.user.is_admin():
            signuplist = signuplist.filter(lecture__created_by=request.user, lecture__status=True).order_by('lecture_id').distinct('lecture_id')

        else:
            signuplist = signuplist.filter(user=request.user.id, lecture__status=True)

        # filter by year & semester
        result = signuplist.filter(lecture__year=str(sortyear), lecture__semester=str(sortsubj))

        if request.user.is_semi_admin():
            signuplist = TALec.union(result.filter(user=request.user.id, lecture__status=True))
            for signup in signuplist:
                if signup in TALec:
                    signup.isallow = True

        elif request.user.is_admin():
            for signup in signuplist:
                signup.isallow = True

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