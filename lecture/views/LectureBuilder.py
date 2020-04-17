from problem.models import Problem
from submission.models import Submission
from lecture.models import signup_class
from lecture.views.LectureAnalysis import lecDispatcher, DataType
from django.db.models import Max
from account.models import AdminType

class LectureBuilder:
    def LectureSubmit(self, submission):
        try:
            lectures = signup_class.objects.filter(isallow=True
                                                  , user=submission.user_id
                                                  , lecture=submission.lecture).select_related('lecture')
            for lec in lectures:
                LectureInfo = lecDispatcher()
                LectureInfo.fromDict(lec.score)
                LectureInfo.associateSubmission(submission)
                lec.score = LectureInfo.toDict()
                lec.save()
        except Exception as e:
            print("Exception :",e)

    def MigrateProblem(self, problem):
        try:
            students = signup_class.objects.filter(isallow=True
                                                  , lecture=problem.contest.lecture).select_related('lecture')

            for student in students:
                linfo = lecDispatcher()
                linfo.fromDict(student.score)
                linfo.migrateProblem(problem)
                student.score = linfo.toDict()
                student.save()
        except Exception as e:
            print("MigrateProblem Exception :",e)

    def MigrateContest(self, contest):
        try:
            print("Migrate Contest")
            students = signup_class.objects.filter(isallow=True
                                                   , lecture=contest.lecture).select_related('lecture')

            for student in students:
                linfo = lecDispatcher()
                linfo.fromDict(student.score)
                linfo.migrateContest(contest)
                student.score = linfo.toDict()
                student.save()
        except Exception as e:
            print("Contest Migrate Exception :", e)

    def DeleteProblem(self, problem):
        try:
            print("Delete Prolem")
            students = signup_class.objects.filter(isallow=True
                                                   , lecture=problem.contest.lecture).select_related('lecture')

            for student in students:
                linfo = lecDispatcher()
                linfo.fromDict(student.score)
                linfo.deleteProblem(problem)
                student.score = linfo.toDict()
                student.save()
        except Exception as e:
            print("MigrateProblem Exception :", e)

    def DeleteContest(self, contest):
        try:
            print("Delete Contest")
            students = signup_class.objects.filter(isallow=True
                                                   , lecture=contest.lecture).select_related('lecture')

            for student in students:
                linfo = lecDispatcher()
                linfo.fromDict(student.score)
                linfo.deleteContest(contest)
                student.score = linfo.toDict()
                student.save()
        except Exception as e:
            print("Contest Delete Exception :", e)

    def buildLectureforAllUser(self, lecture):
        try:
            lectures = signup_class.objects.filter(isallow=True, lecture_id=lecture.id).select_related('lecture').order_by('lecture')
        except Exception as e:
            print("exception", e)
        self.buildLecture(lectures)

    def buildLecture(self, lectures):
        lid = -1
        for lec in lectures:
            if lec.user.admin_type == AdminType.SUPER_ADMIN or lec.user.admin_type == AdminType.ADMIN:
                continue

            plist = Problem.objects.filter(contest__lecture=lec.lecture_id).prefetch_related('contest')

            # test

            LectureInfo = lecDispatcher()
            LectureInfo.fromDict(lec.score)

            for p in plist:
                LectureInfo.migrateProblem(p)

            lec.score = LectureInfo.toDict()
            lec.save()
        print("Lecture Re build finished")