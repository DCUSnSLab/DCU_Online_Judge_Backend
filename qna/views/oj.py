from account.decorators import ensure_qna_access
from lecture.models import Lecture, ta_admin_class
from utils.api import APIView
from ..models import Post, Comment
from problem.models import Problem
from django.db.models import Q
from contest.models import Contest
from submission.models import Submission
from ..serializers import PostListSerializer, PostDetailSerializer, CommentSerializer

'''
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    date_posted = models.DateTimeField(default=timezone.now)
    content = models.TextField()
    author = models.CharField(max_length=200)
'''
class CommentAPI(APIView):
    def get(self, request):
        questionID = request.GET.get("questionID")

        if questionID:
            question = Post.objects.get(id=questionID)
            comment = Comment.objects.filter(post=question).order_by("-date_posted")
            ensure_qna_access(question, request.user)
            return self.success(self.paginate_data(request, comment, CommentSerializer))

    def post(self, request):
        data = request.data
        questionID = data['questionID']
        comment = data['comment']

        if questionID:
            question = Post.objects.get(id=questionID)
            ensure_qna_access(question, request.user)
            comment = Comment.objects.create(post=question, content=comment, author=request.user)
            return self.success(CommentSerializer(comment).data)

    def delete(self, request):
        comment_id = request.GET.get("id")
        if comment_id:
            comment = Comment.objects.get(id=comment_id)
            if comment.author == request.user or request.user.is_super_admin():
                comment.delete()
            elif comment.post.contest is not None:
                if comment.post.contest.lecture.created_by == request.user:
                    comment.delete()
                else:
                    return self.error("작성 본인 또는 관리자만 삭제할 수 있습니다.")
            else:
                return self.error("작성 본인 또는 관리자만 삭제할 수 있습니다.")
        return self.success()



class QnAPostDetailAPI(APIView):
    def post(self, request):
        data = request.data
        questionID = data['questionID']

        if questionID:
            question = Post.objects.get(id=questionID)
            ensure_qna_access(question, request.user)
            question.solved = not question.solved
            question.save()
            return self.success(question.solved)

    def get(self, request):
        questionID = request.GET.get("questionID")

        if questionID:
            question = Post.objects.get(id=questionID)
            ensure_qna_access(question, request.user)
            return self.success(PostDetailSerializer(question).data)

    def delete(self, request):
        questionID = request.GET.get("questionID")

        if questionID:
            question = Post.objects.get(id=questionID)
            if question.author == request.user or request.user.is_super_admin():
                question.delete()
            elif question.contest is not None:
                if question.contest.lecture.created_by == request.user:
                    question.delete()
                else:
                    return self.error("작성 본인 또는 관리자만 삭제할 수 있습니다.")
            else:
                return self.error("작성 본인 또는 관리자만 삭제할 수 있습니다.")

        return self.success()

class QnAPostAPI(APIView):
    def post(self, request):
        data = request.data
        try:
            contest = Contest.objects.get(id=data['contestID'])
            problem = Problem.objects.get(id=data['problemID'])
            submission = Submission.objects.get(id=data['id'])
            qna = Post.objects.create(title=data['content']['title'], content=data['content']['content'], author=request.user, submission=submission, problem=problem, contest=contest)
        except:
            private = data['private']
            if not private:
                qna = Post.objects.create(title=data['content']['title'], content=data['content']['content'], author=request.user, private=False)
            else:
                qna = Post.objects.create(title=data['content']['title'], content=data['content']['content'], author=request.user)

        return self.success()

    def get(self, request):
        # problemID = request.GET.get("problemID")
        lectureID = request.GET.get("LectureID")
        allQuestion = request.GET.get("all")
        #contestID = request.GET.get("contestID")

        if allQuestion == 'all':
            visible = False if (request.GET.get("visible") == 'false') else True
            PostList = Post.objects.filter(solved=visible, private=False)
            if request.user.is_super_admin():
                return self.success(self.paginate_data(request, PostList, PostListSerializer))
            elif request.user.is_admin():
                PostList = PostList.filter(contest__lecture__created_by=request.user)
            elif request.user.is_semi_admin():
                ta_lec_list = ta_admin_class.objects.filter(user=request.user)
                TA_PostList = ''
                for ta_lec in ta_lec_list:
                    if TA_PostList == '':
                        TA_PostList = PostList.filter(contest__lecture=ta_lec.lecture)
                    else:
                        TA_PostList = TA_PostList.union(PostList.filter(contest__lecture=ta_lec.lecture))
                PostList = TA_PostList

            return self.success(self.paginate_data(request, PostList, PostListSerializer))

        elif lectureID:
            lecture = Lecture.objects.get(id=lectureID)
            visible = False if (request.GET.get("visible") == 'false') else True
            PostList = Post.objects.filter(contest__lecture=lecture, solved=visible)
            if request.user.is_admin_role():
                return self.success(self.paginate_data(request, PostList, PostListSerializer))

            PostList = PostList.filter(Q(author=request.user) | Q(private=False))
            return self.success(self.paginate_data(request, PostList, PostListSerializer))

        else:
            if request.user.is_super_admin():
                lecture = Lecture.objects.get(id=lectureID)
                visible = False if (request.GET.get("visible") == 'false') else True
                PostList = Post.objects.filter(contest__lecture=lecture, solved=visible)
                return self.success(self.paginate_data(request, PostList, PostListSerializer))
