from utils.constants import ContestRuleType  # noqa
from django.db import models
from django.utils.timezone import now
from utils.models import JSONField

from account.models import User
from utils.models import RichTextField

class Lecture(models.Model):
    title = models.TextField()
    description = RichTextField()
    created_by_id = models.ForeignKey(User, on_delete = models.CASCADE)
    status = models.BooleanField()

    class Meta:
        db_table = "lecture"

class signup_class(models.Model):
    lecture_id = models.ForeignKey(Lecture, on_delete = models.CASCADE)
    user_id = models.ForeignKey(User, on_delete = models.CASCADE)
