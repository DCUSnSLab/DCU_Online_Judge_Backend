import os
import re
import json
import xlsxwriter

from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import HttpResponse
from django.contrib.auth.hashers import make_password

from submission.models import Submission
from utils.api import APIView, validate_serializer
from utils.shortcuts import rand_str
from lecture.models import Lecture, signup_class
from contest.models import Contest
from problem.models import Problem

from ..decorators import super_admin_required
from ..models import AdminType, ProblemPermission, User, UserProfile
from ..serializers import EditUserSerializer, UserAdminSerializer, GenerateUserSerializer
from ..serializers import ImportUserSeralizer, SignupSerializer
from lecture.serializers import SignupClassSerializer

class UserAdminAPI(APIView):
    @validate_serializer(ImportUserSeralizer)
    @super_admin_required
    def post(self, request):
        """
        Import User
        """
        data = request.data["users"]

        user_list = []
        for user_data in data:
            if len(user_data) != 3 or len(user_data[0]) > 32:
                return self.error(f"Error occurred while processing data '{user_data}'")
            user_list.append(User(username=user_data[0], password=make_password(user_data[1]), email=user_data[2]))

        try:
            with transaction.atomic():
                ret = User.objects.bulk_create(user_list)
                UserProfile.objects.bulk_create([UserProfile(user=user) for user in ret])
            return self.success()
        except IntegrityError as e:
            # Extract detail from exception message
            #    duplicate key value violates unique constraint "user_username_key"
            #    DETAIL:  Key (username)=(root11) already exists.
            return self.error(str(e).split("\n")[1])

    @validate_serializer(EditUserSerializer)
    @super_admin_required
    def put(self, request):
        """
        Edit user api
        """
        data = request.data
        try:
            user = User.objects.get(id=data["id"])
        except User.DoesNotExist:
            return self.error("User does not exist")
        if User.objects.filter(username=data["username"].lower()).exclude(id=user.id).exists():
            return self.error("Username already exists")
        if User.objects.filter(email=data["email"].lower()).exclude(id=user.id).exists():
            return self.error("Email already exists")

        pre_username = user.username
        user.username = data["username"].lower()
        user.email = data["email"].lower()
        user.admin_type = data["admin_type"]
        user.is_disabled = data["is_disabled"]

        if data["admin_type"] == AdminType.ADMIN:
            user.problem_permission = data["problem_permission"]
        elif data["admin_type"] == AdminType.SUPER_ADMIN:
            user.problem_permission = ProblemPermission.ALL
        else:
            user.problem_permission = ProblemPermission.NONE

        if data["password"]:
            user.set_password(data["password"])

        if data["open_api"]:
            # Avoid reset user appkey after saving changes
            if not user.open_api:
                user.open_api_appkey = rand_str()
        else:
            user.open_api_appkey = None
        user.open_api = data["open_api"]

        if data["two_factor_auth"]:
            # Avoid reset user tfa_token after saving changes
            if not user.two_factor_auth:
                user.tfa_token = rand_str()
        else:
            user.tfa_token = None

        user.two_factor_auth = data["two_factor_auth"]

        user.save()
        if pre_username != user.username:
            Submission.objects.filter(username=pre_username).update(username=user.username)

        UserProfile.objects.filter(user=user).update(real_name=data["real_name"])
        return self.success(UserAdminSerializer(user).data)

    @super_admin_required
    def get(self, request):
        """
        수강과목이 있는 학생 목록을 가져오기 위한 기능
        """

        user_id = request.GET.get("id")

        lecture_id = request.GET.get("lectureid")

        if lecture_id: # 특정 수강과목을 수강중인 학생 리스트업 하는 경우
            try:
                ulist = signup_class.objects.select_related('lecture') # lecture_signup_class 테이블의 모든 값, 외래키가 있는 lecture 테이블의 값을 가져온다

            except signup_class.DoesNotExist:
                return self.error("수강중인 학생이 없습니다.")

            contestlist = Contest.objects.select_related('lecture')  # 데이터베이스의 Contest들을 가져온다
            lecturecontest = contestlist.filter(lecture_id=lecture_id)  # 가져온 Contest 중 해당하는 lecture_id를 가진 Contest만 저장한다.

            ulist = ulist.filter(lecture_id=lecture_id)  # 사용자 목록(lecture_signup_class)에서 해당 lecture_id를 가진 사용자를 추려낸다.
            for uu in ulist:
                # print(uu.lecture.description)  # 해당 출력문을 봤을 때, lecture_signup_class테이블이 1단계, lecture 테이블은 2단계에 있는 듯?

                problemSum = 0 # 문제 총 갯수
                problemSolved = 0 # 해결한 문제 갯수
                scoreSum = 0 # 점수 총 합
                scoreMax = 0 # 현재 수강과목의 최대 점수
                problemAvg = 0 # 점수 평균 scoreSum / problemSolved

                for contest in lecturecontest:
                    Problemscore = 0

                    problemlist = Problem.objects.select_related('contest')
                    problemlist = problemlist.filter(contest_id=contest.id) # 전체 문제 중 각 lecturecontes 목록의 contest_id를 가지고 있는 문제를 모두 저장한다.

                    for problem in problemlist:
                        problemtotalScore = 0
                        problemPassed = True
                        problemsubmit = Submission.objects.select_related('problem')
                        submitlist = problemsubmit.filter(user_id=uu.user_id, contest_id=contest.id, problem_id=problem.id)

                        testlist = signup_class.objects.select_related('lecture').select_related(
                            'lecture__created_by')  # lecture_signup_class 1단계, lecture 2단계,
                        submissionlist = Submission.objects.select_related('user')
                        submissionlist = submissionlist.filter(user_id=uu.user_id, problem_id=problem.id)

                        for submit in submitlist:
                            # print("Submission print test",submit.info)
                            Json = submit.info
                            print("json print test",Json)
                            if Json: # 해당 사용자의 submit 이력이 있는 경우 (Submission에 사용자의 id값이 포함된 값이 있는 경우)
                                for jsondata in Json['data']: # result의 값이 0인 테스트 케이스들의 점수만 합한다. 각 문제의 최대 점수는 problem의 total_score 컬럼에 명시되어 있다.
                                    if jsondata['result'] == 0:
                                        problemtotalScore = problemtotalScore + jsondata['score']
                                    else:
                                        problemPassed = False # 테스트 케이스 중 하나라도 통과하지 못했다면, False로 초기화한다.

                                    #if jsondata['score'] > TopScore : # 저장된 점수 중 더 큰 점수값이 있는 경우
                                    #    TopScore = jsondata['score'] # 해당 값을 TopScore에 저장한다.

                        print("problemtotalScore :",problemtotalScore)
                        Problemscore = Problemscore + problemtotalScore # 문제 별 총 점수 : 각 문제에 대해 제출한 결과 중 result가 0인(Success) 값들의 총 합을 더함
                        scoreMax = scoreMax + problem.total_score # Contest에 포함된 각 문제의 최대 점수를 더하여 scoreMax에 저장한다
                        if problemtotalScore != problem.total_score: # 총 점수 != 최대 점수인 경우
                            print("해결 못한 문제임")
                        elif problemPassed == True: # 모든 테스트 케이스를 통과한 경우,
                            problemSolved = problemSolved + 1 # 해결한 문제로 판단하고 값을 1 증가시킨다.

                    scoreSum = scoreSum + Problemscore
                    problemSum = problemSum + problemlist.count() # 각 Contest의 하위 문제가 몇개인지 카운트한다.

                if problemSolved != 0: # problemSolved가 0이 아닌 경우에면 평균값을 구하는 연산 수행       *0으로 나누면 오류 발생
                    problemAvg = scoreSum / problemSolved

                print("문제 총 갯수 :",problemSum)
                print("문제 해결 갯수 :", problemSolved)
                print("총점 :", scoreSum)
                print("최대 총점 :", scoreMax)
                print("평균 :", problemAvg)

                uu.totalProblem = problemSum
                uu.solveProblem = problemSolved
                uu.totalScore = scoreSum
                uu.maxScore = scoreMax
                uu.avgScore = problemAvg

            #return self.success()

            return self.success(self.paginate_data(request, ulist, SignupSerializer))

        """
        User list api / Get user by id
        """

        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return self.error("User does not exist")
            return self.success(UserAdminSerializer(user).data)

        user = User.objects.all().order_by("-create_time")

        keyword = request.GET.get("keyword", None)
        if keyword:
            user = user.filter(Q(username__icontains=keyword) |
                               Q(userprofile__real_name__icontains=keyword) |
                               Q(email__icontains=keyword))
        return self.success(self.paginate_data(request, user, UserAdminSerializer))

    @super_admin_required
    def delete(self, request):
        id = request.GET.get("id")
        if not id:
            return self.error("Invalid Parameter, id is required")
        ids = id.split(",")
        if str(request.user.id) in ids:
            return self.error("Current user can not be deleted")
        User.objects.filter(id__in=ids).delete()
        return self.success()


class GenerateUserAPI(APIView):
    @super_admin_required
    def get(self, request):
        """
        download users excel
        """
        file_id = request.GET.get("file_id")
        if not file_id:
            return self.error("Invalid Parameter, file_id is required")
        if not re.match(r"^[a-zA-Z0-9]+$", file_id):
            return self.error("Illegal file_id")
        file_path = f"/tmp/{file_id}.xlsx"
        if not os.path.isfile(file_path):
            return self.error("File does not exist")
        with open(file_path, "rb") as f:
            raw_data = f.read()
        os.remove(file_path)
        response = HttpResponse(raw_data)
        response["Content-Disposition"] = f"attachment; filename=users.xlsx"
        response["Content-Type"] = "application/xlsx"
        return response

    @validate_serializer(GenerateUserSerializer)
    @super_admin_required
    def post(self, request):
        """
        Generate User
        """
        data = request.data
        number_max_length = max(len(str(data["number_from"])), len(str(data["number_to"])))
        if number_max_length + len(data["prefix"]) + len(data["suffix"]) > 32:
            return self.error("Username should not more than 32 characters")
        if data["number_from"] > data["number_to"]:
            return self.error("Start number must be lower than end number")

        file_id = rand_str(8)
        filename = f"/tmp/{file_id}.xlsx"
        workbook = xlsxwriter.Workbook(filename)
        worksheet = workbook.add_worksheet()
        worksheet.set_column("A:B", 20)
        worksheet.write("A1", "Username")
        worksheet.write("B1", "Password")
        i = 1

        user_list = []
        for number in range(data["number_from"], data["number_to"] + 1):
            raw_password = rand_str(data["password_length"])
            user = User(username=f"{data['prefix']}{number}{data['suffix']}", password=make_password(raw_password))
            user.raw_password = raw_password
            user_list.append(user)

        try:
            with transaction.atomic():

                ret = User.objects.bulk_create(user_list)
                UserProfile.objects.bulk_create([UserProfile(user=user) for user in ret])
                for item in user_list:
                    worksheet.write_string(i, 0, item.username)
                    worksheet.write_string(i, 1, item.raw_password)
                    i += 1
                workbook.close()
                return self.success({"file_id": file_id})
        except IntegrityError as e:
            # Extract detail from exception message
            #    duplicate key value violates unique constraint "user_username_key"
            #    DETAIL:  Key (username)=(root11) already exists.
            return self.error(str(e).split("\n")[1])
