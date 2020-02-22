from utils.constants import ContestRuleType  # noqa
from django.db import models
from django.utils.timezone import now
from utils.models import JSONField

from account.models import User
from utils.models import RichTextField

class Lecture(models.Model):
    title = models.TextField()
    description = RichTextField()
    created_by = models.ForeignKey(User, on_delete = models.CASCADE) #외래키 사용 시 뒤에 자동으로 _id가 붙는다.
    status = models.BooleanField()
    password = models.TextField()
    isapply = models.BooleanField(default=False)
    class Meta:
        db_table = "lecture"

class signup_class(models.Model):
    lecture = models.ForeignKey(Lecture, on_delete = models.CASCADE)
    user = models.ForeignKey(User, on_delete = models.CASCADE)
    status = models.BooleanField(default=False)
    isallow = models.BooleanField(default=False)