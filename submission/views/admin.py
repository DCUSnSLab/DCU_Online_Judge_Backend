from account.decorators import super_admin_required
from judge.tasks import judge_task
# from judge.dispatcher import JudgeDispatcher
from utils.api import APIView
from ..models import Submission
from django.db.models import Count
from django.db.models.functions import TruncDate
from datetime import timedelta, date

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

class SubmissionDataAPI(APIView):
    def get(self, request):
        today = date.today()
        earliest_submission = Submission.objects.earliest('create_time')
        start_date = earliest_submission.create_time.date()

        date_range = [start_date + timedelta(days=i) for i in range((today - start_date).days + 1)]
        submission_counts = Submission.objects.annotate(date=TruncDate('create_time')).values('date').annotate(submission_count=Count('id')).order_by('date')
        
        data = []
        submission_dict = {submission['date']: submission['submission_count'] for submission in submission_counts}

        for single_date in date_range:
            data.append({
                "date": single_date.strftime('%Y-%m-%d'),
                "submission_count": submission_dict.get(single_date, 0)
            })

        return self.success(data)
    
