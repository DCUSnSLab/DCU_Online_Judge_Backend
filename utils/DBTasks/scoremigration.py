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

try:
    print("Try")
    lectures = signup_class.objects.filter(isallow=True).select_related('lecture').order_by('lecture')
except:
    print("exception")

lid = -1
total = lectures.count()
cnt = 0
for lec in lectures:
    cnt += 1
    #if lec.user.realname != '홍도영':
    #    continue

    if lec.user.admin_type == AdminType.SUPER_ADMIN or lec.user.admin_type == AdminType.ADMIN:
        continue

    if lid != lec.lecture_id:
        lid = lec.lecture_id

        plist = Problem.objects.filter(contest__lecture=lec.lecture_id).prefetch_related('contest')

        # test
        LectureInfo = lecDispatcher()
        for p in plist:
            #print(p.id,p.title,p.visible)
            LectureInfo.migrateProblem(p)

    # get Submission
        sublist = Submission.objects.filter(lecture=lec.lecture_id)

    ldates = sublist.filter(user=lec.user).values('contest', 'problem').annotate(latest_created_at=Max('create_time'))
    sdata = sublist.filter(create_time__in=ldates.values('latest_created_at')).order_by('-create_time')
    LectureInfo.cleanDataForScorebard()

    for submit in sdata:
        LectureInfo.associateSubmission(submit)

    # print("Print Lecture Info :",LectureInfo.Info.data[DataType.NUMOFCONTENTS], LectureInfo.Info.data[DataType.NUMOFTOTALPROBLEMS],
    #       LectureInfo.Info.data[DataType.POINT]
    #       ,"/", LectureInfo.Info.data[DataType.NUMOFTOTALSUBPROBLEMS]
    #       ,"|", LectureInfo.Info.data[DataType.AVERAGE], LectureInfo.Info.data[DataType.PROGRESS])
    #
    # for key in LectureInfo.contAnalysis.keys():
    #     print("Contest Type :",key, end=" - ")
    #     contA = LectureInfo.contAnalysis[key]
    #     print("Inform :",contA.Info.data[DataType.POINT]
    #           , contA.Info.data[DataType.NUMOFCONTENTS], contA.Info.data[DataType.NUMOFTOTALPROBLEMS]
    #           , "/",contA.Info.data[DataType.NUMOFTOTALSUBPROBLEMS]
    #           , "|", contA.Info.data[DataType.AVERAGE], contA.Info.data[DataType.PROGRESS])
    #
    #     for cont in contA.contests.values():
    #         print("-- Contest - ",cont.title,":",cont.Info.data[DataType.POINT], cont.Info.data[DataType.NUMOFCONTENTS], cont.Info.data[DataType.NUMOFTOTALPROBLEMS], cont.Info.data[DataType.ISVISIBLE],
    #               "|",cont.Info.data[DataType.AVERAGE],cont.Info.data[DataType.PROGRESS])
    #
    #         for prob in cont.problems.values():
    #             print("----- Prob - ", prob.id, ":", prob.Info.data[DataType.POINT],
    #                   prob.Info.data[DataType.NUMOFCONTENTS], prob.Info.data[DataType.ISVISIBLE],
    #                   "| SCORE:",prob.Info.data[DataType.SCORE])

    # for cont in contA.contests:
    #     print(cont.title,":",cont.Info.point, cont.Info.numofContents)

    #print("--- :",LectureInfo.toDict())

    lec.score = LectureInfo.toDict()
    lec.save()

    print("(", cnt, "/", total, ")", lec.lecture_id, lec.id, lec.user.realname,lec.user.username, lec.lecture.title, 'Completedd')

    # if lec.user.realname=='강동우':
    #     print(lec.score)
    #     LectureInfo.fromDict(lec.score)
    #     break




