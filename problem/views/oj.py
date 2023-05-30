import random
from django.db.models import Q, Count
from utils.api import APIView
from account.decorators import check_contest_permission, ensure_prob_access
from ..models import ProblemTag, Problem, ProblemRuleType
from contest.models import Contest
from lecture.models import signup_class
from ..serializers import ProblemSerializer, TagSerializer, ProblemSafeSerializer, ContestExitSerializer  # working by soojung
from contest.models import ContestRuleType, ContestUser
from django.utils.timezone import now
from account.models import User


class ProblemTagAPI(APIView):
    def get(self, request):
        tags = ProblemTag.objects.annotate(problem_count=Count("problem")).filter(problem_count__gt=0)
        return self.success(TagSerializer(tags, many=True).data)


class PickOneAPI(APIView):
    def get(self, request):
        problems = Problem.objects.filter(contest_id__isnull=True, visible=True)
        count = problems.count()
        if count == 0:
            return self.error("No problem to pick")
        return self.success(problems[random.randint(0, count - 1)]._id)

class Random_By_LevelAPI(APIView):
    def get(self, request):
        user = User.objects.get(id=request.user.id)
        if user.rank_point > 100:
            problems = Problem.objects.filter(contest_id__isnull=True, visible=True, difficulty="High")
            count = problems.count()
        elif user.rank_point > 30:
            problems = Problem.objects.filter(contest_id__isnull=True, visible=True, difficulty="Mid")
            count = problems.count()
        else:
            problems = Problem.objects.filter(contest_id__isnull=True, visible=True, difficulty="Low")
            count = problems.count()

        if count == 0:
            return self.error("No problem to pick")
        return self.success(problems[random.randint(0, count - 1)]._id)



class ProblemAPI(APIView):
    @staticmethod
    def _add_problem_status(request, queryset_values):
        if request.user.is_authenticated:
            profile = request.user.userprofile
            acm_problems_status = profile.acm_problems_status.get("problems", {})
            oi_problems_status = profile.oi_problems_status.get("problems", {})
            # paginate data
            results = queryset_values.get("results")
            if results is not None:
                problems = results
            else:
                problems = [queryset_values, ]
            for problem in problems:
                if problem["rule_type"] == ProblemRuleType.ACM:
                    problem["my_status"] = acm_problems_status.get(str(problem["id"]), {}).get("status")
                else:
                    problem["my_status"] = oi_problems_status.get(str(problem["id"]), {}).get("status")

    def get(self, request):
        # 问题详情页
        problem_id = request.GET.get("problem_id")
        print()
        print(problem_id)
        print()

        if problem_id:
            try:
                problem = Problem.objects.select_related("created_by").get(_id=problem_id, contest_id__isnull=True, visible=True)
                problem_data = ProblemSerializer(problem).data
                self._add_problem_status(request, problem_data)
                return self.success(problem_data)
            except Problem.DoesNotExist:
                return self.error("Problem does not exist")

        limit = request.GET.get("limit")
        if not limit:
            return self.error("Limit is needed")

        problems = Problem.objects.select_related("created_by").filter(contest_id__isnull=True, visible=True)
        # 按照标签筛选
        tag_text = request.GET.get("tag")
        if tag_text:
            problems = problems.filter(tags__name=tag_text)

        # 搜索的情况
        keyword = request.GET.get("keyword", "").strip()
        if keyword:
            problems = problems.filter(Q(title__icontains=keyword) | Q(_id__icontains=keyword))

        # 难度筛选
        difficulty = request.GET.get("difficulty")
        if difficulty:
            problems = problems.filter(difficulty=difficulty)
        # 根据profile 为做过的题目添加标记
        data = self.paginate_data(request, problems, ProblemSerializer)
        self._add_problem_status(request, data)
        return self.success(data)

class ContestProblemAPI(APIView):
    def _add_problem_status(self, request, queryset_values):
        if request.user.is_authenticated:
            profile = request.user.userprofile
            if self.contest.rule_type == ContestRuleType.ACM:
                problems_status = profile.acm_problems_status.get("contest_problems", {})
            else:
                problems_status = profile.oi_problems_status.get("contest_problems", {})
            for problem in queryset_values:
                problem["my_status"] = problems_status.get(str(problem["id"]), {}).get("status")

    @check_contest_permission(check_type="problems")
    def get(self, request):
        problem_id = request.GET.get("problem_id")
        ensure_prob_access(self.contest, request.user)
        if problem_id:
            try:
                problem = Problem.objects.select_related("created_by").get(_id=problem_id, contest=self.contest, visible=True)
            except Problem.DoesNotExist:
                return self.error("Problem does not exist.")
            if self.contest.problem_details_permission(request.user):
                problem_data = ProblemSerializer(problem).data
                self._add_problem_status(request, [problem_data, ])
            else:
                problem_data = ProblemSafeSerializer(problem).data
            return self.success(problem_data)

        contest_problems = Problem.objects.select_related("created_by").filter(contest=self.contest, visible=True)

        #if self.contest.lecture_id and (self.contest.lecture_contest_type == '대회' and self.contest.status == -1):
        if self.contest.problem_details_permission(request.user):
            data = ProblemSerializer(contest_problems, many=True).data
            self._add_problem_status(request, data)
        else:
            data = ProblemSafeSerializer(contest_problems, many=True).data
        return self.success(data)

class ContestExitAccessAPI(APIView):     # working by soojung
    def get(self, request):
        print("ContestExitAccessAPI called")
        contest_id = request.GET.get("contest_id")
        if not contest_id:
            return self.error("Invalid parameter, contest_id is required")
        try:
            user = ContestUser.objects.get(contest_id=contest_id, user_id=request.user.id)
            if user:
                if user.start_time is None:
                    ContestUser.objects.filter(contest_id=contest_id, user_id=request.user.id).update(start_time=now())
                return self.success(ContestExitSerializer(user).data)
        except:
            self.error("Contest %s doesn't exist" % contest)

class ProblemResponsibility(APIView):
    def get(self, request):
        if not request.GET.get("problem_id"):
            return self.error("Parameter error, problem_id is required")

        if request.GET.get("contest_id"):
            try:
                contests = Contest.objects.get(id=request.GET.get("contest_id"))
                if contests.lecture:
                    if request.user.is_admin():
                        return self.success(True)
                        # try:
                        #     signups = signup_class.objects.get(lecture=contests.lecture, user=request.user.id, isallow=True)
                        # except signup_class.DoesNotExist:
                        #     print("Incorrect path")
                        #     return self.success(False)
            except Contest.DoesNotExist:
                return self.error("Parameter error, Contest is required")
        return self.success(True)
