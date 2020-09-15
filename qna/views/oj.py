from account.decorators import ensure_qna_access
from utils.api import APIView
from ..models import Post
from problem.models import Problem
from contest.models import Contest
from submission.models import Submission
from ..serializers import PostListSerializer, PostDetailSerializer

'''
        title = models.CharField(max_length=200)
        content = models.TextField()
        date_posted = models.DateTimeField(default=timezone.now)
        author = models.ForeignKey(User, on_delete=models.CASCADE)
        solved = models.BooleanField(default=False)
        submission = models.ForeignKey(Submission, null=True, on_delete=models.CASCADE)
        lecture = models.ForeignKey(Lecture, null=True, on_delete=models.CASCADE)
'''
class QnAPostDetailAPI(APIView):
    def get(self, request):
        questionID = request.GET.get("questionID")

        if questionID:
            question = Post.objects.get(id=questionID)
            ensure_qna_access(question, request.user)
            return self.success(PostDetailSerializer(question).data)

class QnAPostAPI(APIView):
    def post(self, request):
        data = request.data
        contest = Contest.objects.get(id=data['contestID'])
        problem = Problem.objects.get(id=data['problemID'])
        submission = Submission.objects.get(id=data['id'])
        qna = Post.objects.create(title=data['content']['title'], content=data['content']['content'], author=request.user, submission=submission, problem=problem, contest=contest)
        print(data)
        return self.success()

    def get(self, request):
        # problemID = request.GET.get("problemID")
        # lectureID = request.GET.get("lectureID")
        contestID = request.GET.get("contestID")
        if contestID:
            contest = Contest.objects.get(id=contestID)
            if request.user.is_super_admin():
                visible = False if (request.GET.get("visible") == 'false') else True
                PostList = Post.objects.filter(contest=contest, solved=visible)
                return self.success(self.paginate_data(request, PostList, PostListSerializer))
        else:
            if request.user.is_super_admin():
                visible = False if (request.GET.get("visible") == 'false') else True
                PostList = Post.objects.filter(solved=visible)
                return self.success(self.paginate_data(request, PostList, PostListSerializer))

