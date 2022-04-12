import io

import xlsxwriter
from django.http import HttpResponse
from django.utils.timezone import now
from django.core.cache import cache

from problem.models import Problem
from lecture.models import Lecture, signup_class
from utils.api import APIView, validate_serializer
from utils.constants import CacheKey
from utils.shortcuts import datetime2str, check_is_id
from lecture.views.oj import LectureUtil
from account.models import AdminType
from account.decorators import login_required, check_contest_permission

from utils.constants import ContestRuleType, ContestStatus
from ..models import ContestAnnouncement, Contest, OIContestRank, ACMContestRank, ContestUser
from ..serializers import ContestAnnouncementSerializer
from ..serializers import ContestSerializer, ContestPasswordVerifySerializer
from ..serializers import OIContestRankSerializer, ACMContestRankSerializer

class ContestAnnouncementListAPI(APIView):
    @check_contest_permission(check_type="announcements")
    def get(self, request):
        contest_id = request.GET.get("contest_id")
        if not contest_id:
            return self.error("Invalid parameter, contest_id is required")
        data = ContestAnnouncement.objects.select_related("created_by").filter(contest_id=contest_id, visible=True)
        max_id = request.GET.get("max_id")
        if max_id:
            data = data.filter(id__gt=max_id)
        return self.success(ContestAnnouncementSerializer(data, many=True).data)


class ContestAPI(APIView):
    def get(self, request):
        print("ContestAPI Called")
        id = request.GET.get("id")

        if not id or not check_is_id(id):
            return self.error("Invalid parameter, id is required")
        try:
            contest = Contest.objects.get(id=id, visible=True)
        except Contest.DoesNotExist:
            return self.error("Contest does not exist 12")

        LU = LectureUtil()
        #print("lid = ",contest.lecture_id)
        lecsign = LU.getSignupList(request.user.id, lid=contest.lecture_id)
        #print("lid = ", contest.lecture)
        if not contest.lecture:     # 강의가 아닌 경우
            if contest.private:     # 비공개 대회인 경우
                if request.user.is_super_admin():   # 관리자인 경우 True
                    contest.visible = True
                elif request.user.is_student() or request.user.is_semi_admin():     # 학생이나 준관리자인 경우 True
                    PermitToCont = signup_class.objects.filter(user=request.user, contest=contest)
                    if PermitToCont.exists():
                        contest.visible = True
                    else:
                        return self.error("등록되지 않은 사용자 입니다.")
                else:       # 아무 권한도 아닌 경우 False
                    contest.visible = False
        elif contest.lecture and len(lecsign) != 0 and lecsign[0].isallow:  # 강의가 맞고 & 강의 내 등록된 학생인 경우 True
            #print("Lecture allow : ", lecsign[0].isallow)
            contest.visible = True
        else:
            if request.user.is_admin_role(): # 문제 접근을 위한 visible 값 수정
                contest.visible = True
            else:
                contest.visible = False
        # tuple 생성
        if contest.lecture_contest_type == '대회':
            user = ContestUser.objects.filter(contest_id=id, user_id=request.user.id)
            if not user:
                ContestUser.objects.create(contest_id=id, user_id=request.user.id)

        # working by soojung
        # try:  # 이미 제출한 사용자인지 확인하고, 있는 경우 contest.visible을 False로 변경한다.
        #     user = ContestUser.objects.get(contest_id=contest, user_id=request.user.id)
        #     if user:
        #         if user.is_submitted:
        #             contest.visible = False
        #         else:
        #             contest.visible = True
        # except:
        #         self.error("Contest %s doesn't exist" % contest)

        data = ContestSerializer(contest).data
        data["now"] = datetime2str(now())
        return self.success(data)

class ContestListAPI(APIView):
    def get(self, request):
        print("ContestListAPI Called")
        # contests = Contest.objects.get(lecture=request.get('lecture_id'))
        # return self.success(self.paginate_data(request, contests, ContestSerializer))
        lectureid = request.GET.get('lectureid')
        try:
            lecture = Lecture.objects.get(id=lectureid)
        except:
            print("lecture not exist")
        contests = Contest.objects.select_related("created_by").filter(visible=True, lecture=lectureid)
        if lectureid is None:
            if request.user.is_student():
                access_contest = signup_class.objects.filter(user=request.user, lecture=None)
                permit_cont = []
                for cont in access_contest:
                    if cont.contest in contests:
                        permit_cont.append(cont.contest.id)
                print('permit_cont')

        keyword = request.GET.get("keyword")
        rule_type = request.GET.get("rule_type")
        status = request.GET.get("status")
        if keyword:
            contests = contests.filter(title__contains=keyword)
        if rule_type:
            contests = contests.filter(rule_type=rule_type)
        if status:
            cur = now()
            if status == ContestStatus.CONTEST_NOT_START:
                contests = contests.filter(start_time__gt=cur)
            elif status == ContestStatus.CONTEST_ENDED:
                contests = contests.filter(end_time__lt=cur)
            else:
                contests = contests.filter(start_time__lte=cur, end_time__gte=cur)
        # for contest in contests:
        #    contest.lecture_title = lecture.title
        return self.success(self.paginate_data(request, contests, ContestSerializer))


class ContestPasswordVerifyAPI(APIView):
    @validate_serializer(ContestPasswordVerifySerializer)
    @login_required
    def post(self, request):
        data = request.data
        try:
            contest = Contest.objects.get(id=data["contest_id"], visible=True, password__isnull=False)
        except Contest.DoesNotExist:
            return self.error("Contest does not exist 11")
        if contest.password != data["password"]:
            return self.error("Wrong password")

        # password verify OK.
        if "accessible_contests" not in request.session:
            request.session["accessible_contests"] = []
        request.session["accessible_contests"].append(contest.id)
        # https://docs.djangoproject.com/en/dev/topics/http/sessions/#when-sessions-are-saved
        request.session.modified = True
        return self.success(True)


class ContestAccessAPI(APIView):
    @login_required
    def get(self, request):
        contest_id = request.GET.get("contest_id")
        if not contest_id:
            return self.error()
        return self.success({"access": int(contest_id) in request.session.get("accessible_contests", [])})


class ContestExitAPI(APIView):   # working by soojung
    def get(self, request):
        print("User info : ")
        print(request.user)
        print("User id : ")
        print(request.user.id)
        contest_id = request.GET.get("contest_id")
        if not contest_id:
            return self.error("Invalid parameter, contest_id is required")
        # is_submitted 칼럼 값을 True 변경
        user = ContestUser.objects.get(contest_id=contest_id, user_id=request.user.id)
        if user.end_time is None:
            ContestUser.objects.filter(contest_id=contest_id, user_id=request.user.id).update(end_time=now())
        return self.success(True)
        #
        # contest_id = request.GET.get("contest_id")
        # if not contest_id:
        #     return self.error()
        # return self.success({"access": int(contest_id) in request.session.get("accessible_contests", [])})
        #
        # data = request.data
        # data["created_by"] = request.user
        # lecture = Lecture.objects.create(**data)
        # signup_class.objects.create(lecture_id=data["lecture_id"], user=request.user)
        # return self.success(ContestAnnouncementSerializer(data, many=True).data)
    # def get(self, request):
    #     print("User info : ")
    #     print(request.user)
    #     print("User id : ")
    #     print(request.user.id)
    #
    #
    #     data = request.data
    #     data["created_by"] = request.user
    #     contest = Contest.objects.create(**data)
    #     ContestSubmitUser.objects.create(contest=contest, user=request.user)
    #     return self.success(LectureAdminSerializer(lecture).data)
    #
    #     # try:
    #     #     csu = ContestSubmitUser.objects.filter(user_id=request.user.id)
    #     #     if csu:
    #     #         print(csu)
    #     #     else:
    #     #         print("해당 학생은 제출하지 않았습니다.")
    #     # except ContestSubmitUser.DoesNotExist:
    #     #     return self.error("아무도 제출하지 않았습니다.")


class ContestRankAPI(APIView):
    def get_rank(self):
        if self.contest.rule_type == ContestRuleType.ACM:
            return ACMContestRank.objects.filter(contest=self.contest,
                                                 user__admin_type=AdminType.REGULAR_USER,
                                                 user__is_disabled=False).\
                select_related("user").order_by("-accepted_number", "total_time")
        else:
            return OIContestRank.objects.filter(contest=self.contest,
                                                user__admin_type=AdminType.REGULAR_USER,
                                                user__is_disabled=False). \
                select_related("user").order_by("-total_score")

    def column_string(self, n):
        string = ""
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            string = chr(65 + remainder) + string
        return string

    @check_contest_permission(check_type="ranks")

    def get(self, request):
        download_csv = request.GET.get("download_csv")
        force_refresh = request.GET.get("force_refresh")
        is_contest_admin = request.user.is_authenticated and request.user.is_contest_admin(self.contest)
        if self.contest.rule_type == ContestRuleType.OI:
            serializer = OIContestRankSerializer
        else:
            serializer = ACMContestRankSerializer

        if force_refresh == "1" and is_contest_admin:
            qs = self.get_rank()
        else:
            cache_key = f"{CacheKey.contest_rank_cache}:{self.contest.id}"
            qs = cache.get(cache_key)
            if not qs:
                qs = self.get_rank()
                cache.set(cache_key, qs)

        if download_csv:
            data = serializer(qs, many=True, is_contest_admin=is_contest_admin).data
            contest_problems = Problem.objects.filter(contest=self.contest, visible=True).order_by("_id")
            problem_ids = [item.id for item in contest_problems]

            f = io.BytesIO()
            workbook = xlsxwriter.Workbook(f)
            worksheet = workbook.add_worksheet()
            worksheet.write("A1", "User ID")
            worksheet.write("B1", "Username")
            worksheet.write("C1", "Real Name")
            if self.contest.rule_type == ContestRuleType.OI:
                worksheet.write("D1", "Total Score")
                for item in range(contest_problems.count()):
                    worksheet.write(self.column_string(5 + item) + "1", f"{contest_problems[item].title}")
                for index, item in enumerate(data):
                    worksheet.write_string(index + 1, 0, str(item["user"]["id"]))
                    worksheet.write_string(index + 1, 1, item["user"]["username"])
                    worksheet.write_string(index + 1, 2, item["user"]["real_name"] or "")
                    worksheet.write_string(index + 1, 3, str(item["total_score"]))
                    for k, v in item["submission_info"].items():
                        worksheet.write_string(index + 1, 4 + problem_ids.index(int(k)), str(v))
            else:
                worksheet.write("D1", "AC")
                worksheet.write("E1", "Total Submission")
                worksheet.write("F1", "Total Time")
                for item in range(contest_problems.count()):
                    worksheet.write(self.column_string(7 + item) + "1", f"{contest_problems[item].title}")

                for index, item in enumerate(data):
                    worksheet.write_string(index + 1, 0, str(item["user"]["id"]))
                    worksheet.write_string(index + 1, 1, item["user"]["username"])
                    worksheet.write_string(index + 1, 2, item["user"]["real_name"] or "")
                    worksheet.write_string(index + 1, 3, str(item["accepted_number"]))
                    worksheet.write_string(index + 1, 4, str(item["submission_number"]))
                    worksheet.write_string(index + 1, 5, str(item["total_time"]))
                    for k, v in item["submission_info"].items():
                        worksheet.write_string(index + 1, 6 + problem_ids.index(int(k)), str(v["is_ac"]))

            workbook.close()
            f.seek(0)
            response = HttpResponse(f.read())
            response["Content-Disposition"] = f"attachment; filename=content-{self.contest.id}-rank.xlsx"
            response["Content-Type"] = "application/xlsx"
            return response

        page_qs = self.paginate_data(request, qs)
        page_qs["results"] = serializer(page_qs["results"], many=True, is_contest_admin=is_contest_admin).data
        return self.success(page_qs)
