from utils.constants import ContestRuleType  # noqa
from django.db import models
from django.utils.timezone import now
from utils.models import JSONField
from account.models import User
from utils.models import RichTextField


class Lecture(models.Model):
    title = models.TextField()
    description = RichTextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)  # 외래키 사용 시 뒤에 자동으로 _id가 붙는다.
    year = models.IntegerField()
    semester = models.IntegerField()
    status = models.BooleanField()
    aihelper_status = models.BooleanField(default=False)
    password = models.TextField()
    isapply = models.BooleanField(default=False)
    isallow = models.BooleanField(default=False)

    class Meta:
        db_table = "lecture"


class signup_class(models.Model):
    lecture = models.ForeignKey(Lecture, null=True, on_delete=models.CASCADE)
    contest = models.ForeignKey('contest.Contest', null=True, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    status = models.BooleanField(default=False)
    isallow = models.BooleanField(default=False)
    realname = models.TextField(default=None, null=True)
    schoolssn = models.IntegerField(default=None, null=True)
    score = JSONField(default=dict)
    etc = models.TextField(null=True)

class ta_admin_class(models.Model):
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    realname = models.TextField(default=None, null=True)
    schoolssn = models.IntegerField(default=None, null=True)
    lecture_isallow = models.BooleanField(default=False)
    code_isallow = models.BooleanField(default=False)
    score_isallow = models.BooleanField(default=False)

    @property
    def checklist(self):
        from .serializers import PermitTA
        checklist = list()
        if self.lecture_isallow:
            checklist.append(PermitTA.PROBLEM)
        if self.code_isallow:
            checklist.append(PermitTA.CODE)
        if self.score_isallow:
            checklist.append(PermitTA.SCORE)

        return checklist

    @classmethod
    def is_user_ta(cls, lecture, user):
        """
        해당 강의에서 이 사용자가 TA인지 확인하는 함수
        :param lecture: Lecture 객체
        :param user: User 객체
        :return: True면 TA, False면 TA 아님
        """
        return cls.objects.filter(lecture=lecture, user=user).exists()