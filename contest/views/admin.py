import copy
import os
import zipfile
from ipaddress import ip_network

import dateutil.parser
from django.http import FileResponse
from django.db.models import Count, Q
from account.decorators import check_contest_permission, ensure_created_by
from account.models import User
from lecture.serializers import LectureSerializer
from lecture.views.LectureBuilder import LectureBuilder, ContestBuilder, ProblemBuilder, UserBuilder
from submission.models import Submission, JudgeStatus
from utils.api import APIView, validate_serializer
from utils.cache import cache
from utils.constants import CacheKey
from utils.shortcuts import rand_str
from utils.tasks import delete_files
from problem.models import Problem
from lecture.models import Lecture, ta_admin_class, signup_class
from contest.models import ContestUser
from ..models import Contest, ContestAnnouncement, ACMContestRank
from ..serializers import (ContestAnnouncementSerializer, ContestAdminSerializer,
                           CreateContestSeriaizer, CreateContestAnnouncementSerializer,
                           EditContestSeriaizer, EditContestAnnouncementSerializer,
                           ACMContesHelperSerializer, AddLectureContestSerializer, )


class ContProblemAPI(APIView):
    def post(self, request):
        print("test2!")

    def get(self, request):
        from problem.serializers import ProblemAdminSerializer
        contest_id = request.GET.get("id")
        cont = Contest.objects.get(id=contest_id)
        p_list = Problem.objects.filter(contest=cont)
        #ensure_created_by(p_list, request.user)

        return self.success(self.paginate_data(request, p_list, ProblemAdminSerializer))

class ContestAPI(APIView):
    @validate_serializer(CreateContestSeriaizer) # 해당 함수를 호출하기 전에, CreateContestSerializer에서 사전 정의되지 않은 값은 통과시키지 않는다.
    def post(self, request):
        print("ContestAPI post")
        data = request.data
        data["start_time"] = dateutil.parser.parse(data["start_time"])
        data["end_time"] = dateutil.parser.parse(data["end_time"])

        if data["lecture_id"] is None: # 해당 Contest가 개설과목에 소속되지 않은 경우
            data["created_by"] = request.user # 요청한 사용자의 id를 created_by에 넣는다.
        else: # 특정 개설과목 하위 목록에서 Create를 통해 Contest를 생성한 경우,
            lecture = Lecture.objects.get(id=data["lecture_id"])
            data["created_by"] = lecture.created_by # 해당 개설과목을 생성한 사용자의 user id를 추가한다.

        if data["end_time"] <= data["start_time"]:
            return self.error("Start time must occur earlier than end time")
        if data.get("password") and data["password"] == "":
            data["password"] = None
        for ip_range in data["allowed_ip_ranges"]:
            try:
                ip_network(ip_range, strict=False)
            except ValueError:
                return self.error(f"{ip_range} is not a valid cidr network")
        contest = Contest.objects.create(**data)

        if data["lecture_contest_type"] == '대회':  # 해당 과목 내 모든 학생에 대한 tuple 생성
            contest_id = Contest.objects.latest('id')
            students = signup_class.objects.filter(lecture_id=data["lecture_id"], contest_id=contest_id, isallow=True, schoolssn__isnull=False)
            for student in students:
                ContestUser.objects.create(contest_id=contest_id.id, user_id=student.user_id, start_time=None, end_time=None)
        return self.success(ContestAdminSerializer(contest).data)

    @validate_serializer(EditContestSeriaizer)
    def put(self, request):
        print("ContestAPI put")
        data = request.data
        print(data)
        try:
            contest = Contest.objects.get(id=data.pop("id"))
            ensure_created_by(contest, request.user)
        except Contest.DoesNotExist:
            return self.error("Contest does not exist 10")
        data["start_time"] = dateutil.parser.parse(data["start_time"])
        data["end_time"] = dateutil.parser.parse(data["end_time"])
        if data["end_time"] <= data["start_time"]:
            return self.error("Start time must occur earlier than end time")
        if not data["password"]:
            data["password"] = None
        for ip_range in data["allowed_ip_ranges"]:
            try:
                ip_network(ip_range, strict=False)
            except ValueError:
                return self.error(f"{ip_range} is not a valid cidr network")
        if not contest.real_time_rank and data.get("real_time_rank"):
            cache_key = f"{CacheKey.contest_rank_cache}:{contest.id}"
            cache.delete(cache_key)

        for k, v in data.items():
            setattr(contest, k, v)

        #contest 값 업데이트
        lb = ContestBuilder(contest)
        lb.MigrateContent()
        contest.save()

        import timeit

        start = timeit.default_timer()
        #lb.doAssociateTask()
        stop = timeit.default_timer()

        print('Time: ', stop - start)
        '''
        all_student = UserBuilder(contest)
        alst = all_student.getLecAllUserList(contest.lecture_id)
        
        for st in alst:
            print(st.realname)
        '''
        return self.success(ContestAdminSerializer(contest).data)

    def get(self, request):
        contest_keyword = request.GET.get("keyword")
        contest_id = request.GET.get("id")
        contest_year = request.GET.get("year")
        contest_semester = request.GET.get("semester")
        show_publicProb = request.GET.get("publicProb")

        #if contest_year: # contest_year가 존재하는 경우 (Add From Public Contest 페이지 Dropdown 값)
        #    contests = Contest.objects.all().order_by("-create_time")
        #    if int(contest_year) > 2000: # 년도 값이 유효한 경우, (기본값인 0이 아닌 경우)
        #        contests = contests.filter(create_time__year=contest_year) # 페이지로부터 년도에 관련된 값을 전달받은 경우, 해당 년도에 해당하는 contest들만 리턴한다.


            #교수일 경우 교수 자신이 생성한 과목만 들고 올 수 있도록 활성화
        #    if request.user.is_admin():
        #        contests = contests.filter(created_by=request.user)
        #    return self.success(self.paginate_data(request, contests, ContestAdminSerializer))

        if contest_id:
            try:
                contest = Contest.objects.get(id=contest_id)
                ensure_created_by(contest, request.user)
                return self.success(ContestAdminSerializer(contest).data)
            except Contest.DoesNotExist:
                return self.error("Contest does not exist 9")

        contests = Contest.objects.all()
        #contests = contests.filter(Q(id=521) |Q(id=522))
        if request.user.is_admin(): # 요청자가 super admin이 아닌 경우, 본인이 생성한 실습, 과제, 대회만 출력하게 하는 부분
           contests = contests.filter(created_by=request.user)


        elif request.user.is_semi_admin():
            # user_permit_lec = Lecture.objects.filter(permit_to__has_keys=[str(request.user.id)])
            user_permit_lec = ta_admin_class.objects.filter(user__id=request.user.id)
            taCont = ''
            for lec in user_permit_lec:
                if taCont == '' and lec.lecture_isallow:
                    taCont = contests.filter(lecture=lec.lecture)
                elif lec.lecture_isallow:
                    taCont = taCont.union(contests.filter(lecture=lec.lecture))
            contests = taCont

            #print(user_permit_lec)
            #user_permit_lec

        keyword = request.GET.get("keyword")

        if show_publicProb:
            contests = Contest.objects.all()

        if contest_year:
            contests = contests.filter(create_time__year=contest_year) # 페이지로부터 년도에 관련된 값을 전달받은 경우, 해당 년도에 해당하는 contest들만 리턴한다.

        if contest_semester:
            contests = contests.filter(lecture__semester=contest_semester)  # 페이지로부터 년도에 관련된 값을 전달받은 경우, 해당 년도에 해당하는 contest들만 리턴한다.

        if keyword:
            contests = contests.filter(title__contains=keyword)

        del_list = []

        contests = contests.order_by("lecture__title", "title", "-create_time")
        for contest in contests:
            if contest.lecture == None: # 수강과목 id가 없는 경우
                del_list.append(contest.id) # 별도의 list에 수강과목 id가 없는 강의의 id를 추가한다.

        if contests == '' or contests.count() < 1:
            return self.success()

        # for idx in del_list: # 이후 해당 리스트에 존재하는 id들을
        #     contests = contests.exclude(id=idx) # contests 쿼리셋에서 제외한다.

        # for contest in contests: # 수강과목이 존재하는 강의는 출력하지 않습니다.
        #     try:
        #         lecture_title = Lecture.objects.get(contest=contest.id)
        #         contest.lecture_title = lecture_title.title
        #     except Exception as e:
        #         print("Contest Get Error:",e)

        return self.success(self.paginate_data(request, contests, ContestAdminSerializer))

    def delete(self, request):
        id = request.GET.get("id")
        if not id:
            return self.error("Invalid Parameter, id is required")
        conts = Contest.objects.filter(id=id)
        if conts:
            for cont in conts:
                lb = ContestBuilder(cont)
                lb.DeleteContent()
            conts.delete()
        return self.success()

class LectureContestAPI(APIView):
    def get(self, request):
        #print("Lecture Contest API Start")
        contest_id = request.GET.get("contest_id")
        lecture_id = request.GET.get("lecture_id")
        user = request.user
        if not lecture_id:
            return self.error("Lecture id is required")
        try:
            lecture = Lecture.objects.get(id=lecture_id)
            ensure_created_by(lecture, user)
        except Contest.DoesNotExist:
            return self.error("Contest does not exist 8")
        contests = Contest.objects.filter(lecture=lecture).order_by("-create_time")

        if user.is_admin():
            contests = contests.filter(lecture__created_by=user)
        keyword = request.GET.get("keyword")
        if keyword:
            contests = contests.filter(title__contains=keyword)

        # problem_id = request.GET.get("id")
        # contest_id = request.GET.get("contest_id")
        # user = request.user
        # if problem_id:
        #     try:
        #         problem = Problem.objects.get(id=problem_id)
        #         ensure_created_by(problem.contest, user)
        #     except Problem.DoesNotExist:
        #         return self.error("Problem does not exist")
        #     return self.success(ProblemAdminSerializer(problem).data)
        #
        # if not contest_id:
        #     return self.error("Contest id is required")
        # try:
        #     contest = Contest.objects.get(id=contest_id)
        #     ensure_created_by(contest, user)
        # except Contest.DoesNotExist:
        #     return self.error("Contest does not exist")
        # problems = Problem.objects.filter(contest=contest).order_by("-create_time")
        # if user.is_admin():
        #     problems = problems.filter(contest__created_by=user)
        # keyword = request.GET.get("keyword")
        # if keyword:
        #     problems = problems.filter(title__contains=keyword)
        # return self.success(self.paginate_data(request, problems, ProblemAdminSerializer))
        return self.success(self.paginate_data(request, contests, ContestAdminSerializer))

class ContestAnnouncementAPI(APIView):
    @validate_serializer(CreateContestAnnouncementSerializer)
    def post(self, request):
        """
        Create one contest_announcement.
        """
        data = request.data
        try:
            contest = Contest.objects.get(id=data.pop("contest_id"))
            ensure_created_by(contest, request.user)
            data["contest"] = contest
            data["created_by"] = request.user
        except Contest.DoesNotExist:
            return self.error("Contest does not exist 7")
        announcement = ContestAnnouncement.objects.create(**data)
        return self.success(ContestAnnouncementSerializer(announcement).data)

    @validate_serializer(EditContestAnnouncementSerializer)
    def put(self, request):
        """
        update contest_announcement
        """
        data = request.data
        try:
            contest_announcement = ContestAnnouncement.objects.get(id=data.pop("id"))
            ensure_created_by(contest_announcement, request.user)
        except ContestAnnouncement.DoesNotExist:
            return self.error("Contest announcement does not exist")
        for k, v in data.items():
            setattr(contest_announcement, k, v)
        contest_announcement.save()
        return self.success()

    def delete(self, request):
        """
        Delete one contest_announcement.
        """
        contest_announcement_id = request.GET.get("id")
        if contest_announcement_id:
            if request.user.is_admin():
                ContestAnnouncement.objects.filter(id=contest_announcement_id,
                                                   contest__created_by=request.user).delete()
            else:
                ContestAnnouncement.objects.filter(id=contest_announcement_id).delete()
        return self.success()

    def get(self, request):
        """
        Get one contest_announcement or contest_announcement list.
        """
        contest_announcement_id = request.GET.get("id")
        if contest_announcement_id:
            try:
                contest_announcement = ContestAnnouncement.objects.get(id=contest_announcement_id)
                ensure_created_by(contest_announcement, request.user)
                return self.success(ContestAnnouncementSerializer(contest_announcement).data)
            except ContestAnnouncement.DoesNotExist:
                return self.error("Contest announcement does not exist")

        contest_id = request.GET.get("contest_id")
        if not contest_id:
            return self.error("Parameter error")
        contest_announcements = ContestAnnouncement.objects.filter(contest_id=contest_id)
        if request.user.is_admin():
            contest_announcements = contest_announcements.filter(created_by=request.user)
        keyword = request.GET.get("keyword")
        if keyword:
            contest_announcements = contest_announcements.filter(title__contains=keyword)
        return self.success(ContestAnnouncementSerializer(contest_announcements, many=True).data)


class ACMContestHelper(APIView):
    @check_contest_permission(check_type="ranks")
    def get(self, request):
        ranks = ACMContestRank.objects.filter(contest=self.contest, accepted_number__gt=0) \
            .values("id", "user__username", "user__userprofile__real_name", "submission_info")
        results = []
        for rank in ranks:
            for problem_id, info in rank["submission_info"].items():
                if info["is_ac"]:
                    results.append({
                        "id": rank["id"],
                        "username": rank["user__username"],
                        "real_name": rank["user__userprofile__real_name"],
                        "problem_id": problem_id,
                        "ac_info": info,
                        "checked": info.get("checked", False)
                    })
        results.sort(key=lambda x: -x["ac_info"]["ac_time"])
        return self.success(results)

    @check_contest_permission(check_type="ranks")
    @validate_serializer(ACMContesHelperSerializer)
    def put(self, request):
        data = request.data
        try:
            rank = ACMContestRank.objects.get(pk=data["rank_id"])
        except ACMContestRank.DoesNotExist:
            return self.error("Rank id does not exist")
        problem_rank_status = rank.submission_info.get(data["problem_id"])
        if not problem_rank_status:
            return self.error("Problem id does not exist")
        problem_rank_status["checked"] = data["checked"]
        rank.save(update_fields=("submission_info",))
        return self.success()


class DownloadContestSubmissions(APIView):
    def _dump_submissions(self, contest, exclude_admin=True):
        problem_ids = contest.problem_set.all().values_list("id", "_id")
        id2display_id = {k[0]: k[1] for k in problem_ids}
        ac_map = {k[0]: False for k in problem_ids}
        submissions = Submission.objects.filter(contest=contest, result=JudgeStatus.ACCEPTED).order_by("-create_time")
        user_ids = submissions.values_list("user_id", flat=True)
        users = User.objects.filter(id__in=user_ids)
        path = f"/tmp/{rand_str()}.zip"
        with zipfile.ZipFile(path, "w") as zip_file:
            for user in users:
                if user.is_admin_role() and exclude_admin:
                    continue
                user_ac_map = copy.deepcopy(ac_map)
                user_submissions = submissions.filter(user_id=user.id)
                for submission in user_submissions:
                    problem_id = submission.problem_id
                    if user_ac_map[problem_id]:
                        continue
                    file_name = f"{user.username}_{id2display_id[submission.problem_id]}.txt"
                    compression = zipfile.ZIP_DEFLATED
                    zip_file.writestr(zinfo_or_arcname=f"{file_name}",
                                      data=submission.code,
                                      compress_type=compression)
                    user_ac_map[problem_id] = True
        return path

    def get(self, request):
        contest_id = request.GET.get("contest_id")
        if not contest_id:
            return self.error("Parameter error")
        try:
            contest = Contest.objects.get(id=contest_id)
            ensure_created_by(contest, request.user)
        except Contest.DoesNotExist:
            return self.error("Contest does not exist 6")

        exclude_admin = request.GET.get("exclude_admin") == "1"
        zip_path = self._dump_submissions(contest, exclude_admin)
        delete_files.send_with_options(args=(zip_path,), delay=300_000)
        resp = FileResponse(open(zip_path, "rb"))
        resp["Content-Type"] = "application/zip"
        resp["Content-Disposition"] = f"attachment;filename={os.path.basename(zip_path)}"
        return resp

class AddLectureAPI(APIView):
    #@validate_serializer(AddLectureContestSerializer)
    def get(self, request):
        data = request.data
        user = request.user

        if not data['lecture_id']:
            return self.error("Lecture id is required")
        try:
            lecture = Lecture.objects.get(id=data['lecture_id'])
            ensure_created_by(lecture, user)
        except Lecture.DoesNotExist:
            return self.error("Lecture does not exist")

        if data['showPublic'] == 'true':
            lecture_list = Lecture.objects.all()
        else:
            if user.is_super_admin():
                lecture_list = Lecture.objects.all().filter(year=data['year'], semester=data['semester'])
            elif user.is_admin():
                lecture_list = Lecture.objects.filter(created_by__id=user.id, year=data['year'], semester=data['semester'])
            #elif user.is_semi_admin():

        keyword = request.GET.get('keyword')
        if keyword:
            lecture_list = lecture_list.filter(title__contains=keyword)

        return self.success(self.paginate_data(request, lecture_list, LectureSerializer))

    def post(self, request):
        selectLectureID = request.GET.get('selectLectureID')
        LectureID = request.GET.get('lecture_id')

        from datetime import datetime
        lecture = Lecture.objects.get(id=LectureID)
        copyContList = Contest.objects.filter(lecture__id=selectLectureID)
        date_str = datetime.today().strftime("%Y-%m-%d %H:%M:%S") + '+00'

        from datetime import datetime
        date_str = datetime.today().strftime("%Y-%m-%d %H:%M:%S") + '+00'

        for contest in reversed(copyContList):
            problems = Problem.objects.filter(contest=contest)

            print("Contest 만든 사람 :", contest.created_by)
            contest.pk = None
            contest.created_by = lecture.created_by
            contest.lecture = lecture
            contest.start_time = date_str
            contest.end_time = date_str
            contest.save()

            for problem in problems:
                print(problem.title)
                tags = problem.tags.all()
                problem.pk = None
                problem.created_by = contest.created_by
                problem.contest = contest
                problem.is_public = True
                problem.visible = True
                #problem._id = str(lecture.id)+"_"+problem._id
                problem.submission_number = problem.accepted_number = 0
                problem.statistic_info = {}
                problem.save()

                lb = ProblemBuilder(problem)
                lb.MigrateContent()

                problem.tags.set(tags)

        return self.success()

class AddLectureContestAPI(APIView):
    @validate_serializer(AddLectureContestSerializer)
    def post(self, request):
        data = request.data
        try:
            contest = Contest.objects.get(id=data["contest_id"])
            lecture = Lecture.objects.get(id=data["lecture_id"])
            select_prob = data["prob_id"]
        except (Contest.DoesNotExist):
            return self.error("Contest does not exist 4")

        from datetime import datetime
        date_str = datetime.today().strftime("%Y-%m-%d %H:%M:%S") + '+00'
        #print(date_str)

        if len(select_prob):
            # Contest Copy
            contest.pk = None
            contest.created_by = lecture.created_by
            contest.lecture = lecture
            contest.start_time = date_str
            contest.end_time = date_str
            contest.save()
            # Select prob Copy
            for prob in select_prob:
                problems = Problem.objects.get(id=prob)
                print("Contest 만든 사람 :", contest.created_by)

                tags = problems.tags.all()
                problems.pk = None
                problems.created_by = contest.created_by
                problems.contest = contest
                problems.is_public = True
                problems.visible = True
                # problem._id = str(lecture.id)+"_"+problem._id
                problems.submission_number = problems.accepted_number = 0
                problems.statistic_info = {}

                # copy dataset create
                while True:
                    test_case_id = rand_str()  # create new id
                    from django.conf import settings
                    test_case_dir = os.path.join(settings.TEST_CASE_DIR, test_case_id)
                    origin_test_case_dir = os.path.join(settings.TEST_CASE_DIR, problems.test_case_id)
                    if not os.path.isdir(test_case_dir):
                        os.mkdir(test_case_dir)
                        import shutil
                        shutil.copytree(origin_test_case_dir, test_case_dir)  # copy_dataset
                        break

                os.chmod(test_case_dir, 0o710)
                print(problems.test_case_id, test_case_id)
                problems.test_case_id = test_case_id
                # copy dataset done

                problems.save()

                lb = ProblemBuilder(problems)
                lb.MigrateContent()

                problems.tags.set(tags)

            return self.success()
        else:
            problems = Problem.objects.filter(contest=contest)

            print("Contest 만든 사람 :",contest.created_by)
            contest.pk = None
            contest.created_by = lecture.created_by
            contest.lecture = lecture
            contest.start_time = date_str
            contest.end_time = date_str
            contest.save()

            for problem in problems:
                print(problem.title)

                tags = problem.tags.all()
                problem.pk = None
                problem.created_by = contest.created_by
                problem.contest = contest
                problem.is_public = True
                problem.visible = True
                problem.submission_number = problem.accepted_number = 0
                problem.statistic_info = {}

                # copy dataset create
                while True:
                    test_case_id = rand_str() # create new id
                    from django.conf import settings
                    test_case_dir = os.path.join(settings.TEST_CASE_DIR, test_case_id)
                    origin_test_case_dir = os.path.join(settings.TEST_CASE_DIR, problem.test_case_id)
                    if not os.path.isdir(test_case_dir):
                        # os.mkdir(test_case_dir)
                        import shutil
                        shutil.copytree(origin_test_case_dir, test_case_dir) # copy_dataset
                        break

                os.chmod(test_case_dir, 0o710)
                print(problem.test_case_id, test_case_id)
                problem.test_case_id = test_case_id
                # copy dataset done

                problem.save()

                lb = ProblemBuilder(problem)
                lb.MigrateContent()

                problem.tags.set(tags)

            return self.success()