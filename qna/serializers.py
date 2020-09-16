from problem.serializers import ProblemAdminSerializer
from submission.serializers import SubmissionModelSerializer
from utils.api import serializers
from .models import Post
from account.serializers import UserSerializer
from contest.serializers import ContestAdminSerializer


class PostListSerializer(serializers.ModelSerializer):
    author = UserSerializer()
    problem = ProblemAdminSerializer()

    class Meta:
        model = Post
        fields = "__all__"


class PostDetailSerializer(PostListSerializer):
    submission = SubmissionModelSerializer()
