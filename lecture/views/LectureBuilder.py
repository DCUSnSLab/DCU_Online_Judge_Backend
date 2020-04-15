from problem.models import Problem
from submission.models import Submission
from lecture.models import signup_class
from lecture.views.LectureAnalysis import lecDispatcher, DataType
from django.db.models import Max
from account.models import AdminType

class LectureBuilder:
    def buildLecture(self, lecture):
        try:
            lectures = signup_class.objects.filter(isallow=True, lecture_id=lecture.id).select_related('lecture').order_by('lecture')
        except Exception as e:
            print("exception", e)

        lid = -1
        for lec in lectures:
            if lec.user.admin_type == AdminType.SUPER_ADMIN or lec.user.admin_type == AdminType.ADMIN:
                continue

            # if lid != lec.lecture_id:
            #     lid = lec.lecture_id

            plist = Problem.objects.filter(contest__lecture=lec.lecture_id).prefetch_related('contest')

            # test

            LectureInfo = lecDispatcher()
            LectureInfo.fromDict(lec.score)

            for p in plist:
                # print(p.id,p.title,p.visible)
                LectureInfo.migrateProblem(p)

            lec.score = LectureInfo.toDict()
            lec.save()
        print("Lecture Re build finished")