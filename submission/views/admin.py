from account.decorators import super_admin_required
from judge.tasks import judge_task
# from judge.dispatcher import JudgeDispatcher
from utils.api import APIView
from ..models import Submission

class SubmissionRejudgeAPI(APIView):
    @super_admin_required
    def get(self, request):
        id = request.GET.get("id")
        if not id:
            return self.error("Parameter error, id is required")
        try:
            submission = Submission.objects.select_related("problem").get(id=id, contest_id__isnull=True)
        except Submission.DoesNotExist:
            return self.error("Submission does not exists")
        submission.statistic_info = {}
        submission.save()

        judge_task.send(submission.id, submission.problem.id)
        return self.success()

class SubmissionUpdater(APIView):
    @super_admin_required
    def get(self, request):
        subb = Submission.objects.all()

        i = 0
        for sub in subb:
            if sub.contest_id is not None and sub.lecture_id is None:
                sub.lecture_id = sub.contest.lecture_id
                sub.save()
                print(i, sub.problem.title, sub.contest_id, sub.lecture_id, sub.contest.lecture_id)

            #if i % 100 == 0:
            #    print(i,sub.id,sub.problem.title)
            i+=1
        return self.success()

class SubmissionDateAPI(APIView):
    def get(self, request):
        # 'create_time'에서 날짜 부분만 추출하고, 날짜별로 제출 수 집계
        submission_counts = Submission.objects.annotate(date=TruncDate('create_time')).values('date').annotate(submission_count=Count('id')).order_by('date')

        # 결과를 [{"date": "YYYY-MM-DD", "submission_count": int}, ...] 형식으로 변환
        data = [{"date": submission['date'].strftime('%Y-%m-%d'), "submission_count": submission['submission_count']} for submission in submission_counts]
        
        return self.success(data)