# Create your models here.
from django.db import models
from django.utils import timezone
from account.models import User
from django.urls import reverse
from utils.models import JSONField
from submission.models import Submission
from lecture.models import Lecture
from problem.models import Problem
from contest.models import Contest


# Create your models here.
class Post(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    date_posted = models.DateTimeField(default=timezone.now)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    solved = models.BooleanField(default=False)
    submission = models.ForeignKey(Submission, null=True, on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, null=True, on_delete=models.CASCADE)
    problem = models.ForeignKey(Problem, null=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('post-detail', kwargs={'pk': self.pk})

    class Meta:
        db_table = "qna_post"


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    date_posted = models.DateTimeField(default=timezone.now)
    content = models.TextField()
    author = models.CharField(max_length=200)

    def __str__(self):
        return self.title
