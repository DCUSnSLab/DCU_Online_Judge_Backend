from problem.serializers import ProblemAdminSerializer
from submission.serializers import SubmissionModelSerializer
from utils.api import serializers
from .models import Post, Comment
from account.serializers import UserSerializer
from contest.serializers import ContestAdminSerializer


class CommentSerializer(serializers.ModelSerializer):
    author = UserSerializer()
    permit = serializers.CharField(allow_blank=True, allow_null=True)

    class Meta:
        model = Comment
        fields = "__all__"


class PostListSerializer(serializers.ModelSerializer):
    author = UserSerializer()
    problem = ProblemAdminSerializer()

    class Meta:
        model = Post
        fields = "__all__"


class PostDetailSerializer(PostListSerializer):
    submission = SubmissionModelSerializer()
