import os
import sys
import json
import django

sys.path.append("../../")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oj.settings")
django.setup()

from django.conf import settings
from problem.models import Problem
from submission.models import Submission
from lecture.models import signup_class
from lecture.views.LectureAnalysis import lecDispatcher, DataType
from django.db.models import Max
from account.models import AdminType

subb = Submission.objects.all()

i = 0
for sub in subb:
    #print(i, sub)
    if sub.contest_id is not None and sub.lecture_id is None:
        sub.lecture_id = sub.contest.lecture_id
        sub.save()
        print(i, sub.problem.title, sub.contest_id, sub.lecture_id, sub.contest.lecture_id)

    # if i % 100 == 0:
    #    print(i,sub.id,sub.problem.title)
    i += 1