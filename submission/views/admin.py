from account.decorators import super_admin_required
from judge.tasks import judge_task
# from judge.dispatcher import JudgeDispatcher
from utils.api import APIView
from ..models import Submission
from ..serializers import SubmissionDataSerializer

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
        submission = Submission.objects.all().only('id', 'create_time')
        
        serializer = SubmissionDataSerializer(submission, many=True)

        return self.success(serializer.data)