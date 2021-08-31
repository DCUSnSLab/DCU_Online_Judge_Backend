from django.db.models import Max

from lecture.models import signup_class
from lecture.views.LectureAnalysis import lecDispatcher
from problem.models import Problem
from submission.models import Submission

import datetime

def migrate():
    year = datetime.today().year
    semester = (8 > datetime.today().month >= 3) and 1 or (3 > datetime.today().month >= 1) and 3 or 2

    try:
        print("Try")
        lectures = signup_class.objects.filter(isallow=True, lecture__year=year, lecture__semester=semester).select_related('lecture').order_by('lecture')
        lid = -1
        total = lectures.count()
        cnt = 0
        for lec in lectures:
            try:
                cnt += 1

                if lid != lec.lecture_id:
                    lid = lec.lecture_id

                    plist = Problem.objects.filter(contest__lecture=lec.lecture_id).prefetch_related('contest')

                    # test
                    LectureInfo = lecDispatcher()
                    for p in plist:
                        LectureInfo.migrateProblem(p)

                    # get Submission
                    sublist = Submission.objects.filter(lecture=lec.lecture_id)

                ldates = sublist.filter(user=lec.user).values('contest', 'problem').annotate(
                    latest_created_at=Max('create_time'))
                sdata = sublist.filter(create_time__in=ldates.values('latest_created_at')).order_by('-create_time')
                LectureInfo.cleanDataForScorebard()

                for submit in sdata:
                    LectureInfo.associateSubmission(submit)

                lec.score = LectureInfo.toDict()
                lec.save()

                print("(", cnt, "/", total, ")", lec.lecture_id, lec.id, lec.user.realname, lec.user.username,
                      lec.lecture.title, 'Completedd')
            except:
                print("exception")

    except:
        print("exception")