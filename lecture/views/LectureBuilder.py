from abc import ABCMeta, abstractmethod
from problem.models import Problem
from submission.models import Submission
from lecture.models import signup_class
from lecture.views.LectureAnalysis import lecDispatcher, DataType
from django.db.models import Max
from account.models import AdminType

class TaskType:
    MIGRATE = 1
    DELETE = 2

class LectureBuilder(metaclass=ABCMeta):
    def __init__(self, mainQuery):
        self.MainQuery = mainQuery

    @abstractmethod
    def getLecture(self):
        pass

    @abstractmethod
    def doMigrateTask(self, lecDispatcher):
        pass

    @abstractmethod
    def doDeleteTask(self, lecDispatcher):
        pass

    #Need to update as like doTask()
    def LectureSubmit(self):
        try:
            lectures = signup_class.objects.filter(isallow=True
                                                  , user=self.MainQuery.user_id
                                                  , lecture=self.getLecture()).select_related('lecture')
            for lec in lectures:
                LectureInfo = lecDispatcher()
                LectureInfo.fromDict(lec.score)
                LectureInfo.associateSubmission(self.MainQuery)
                lec.score = LectureInfo.toDict()
                lec.save()
        except Exception as e:
            print("Exception :",e)

    def MigrateContent(self):
        self.doTask(TaskType.MIGRATE)

    def DeleteContent(self):
        self.doTask(TaskType.DELETE)

    def doTask(self, tasktype):
        try:
            students = signup_class.objects.filter(isallow=True
                                                  , lecture=self.getLecture()).select_related('lecture')

            for student in students:
                linfo = lecDispatcher()
                linfo.fromDict(student.score)

                #do task by tasktype
                if tasktype == TaskType.MIGRATE:
                    self.doMigrateTask(linfo)
                elif tasktype == TaskType.DELETE:
                    self.doDeleteTask(linfo)

                student.score = linfo.toDict()
                student.save()
        except Exception as e:
            print(tasktype,"-",self.MainQuery," Exception :",e)

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

class SubmitBuilder(LectureBuilder):
    def __init__(self, submit):
        LectureBuilder.__init__(self, submit)

    def getLecture(self):
        return self.MainQuery.lecture

    def doMigrateTask(self, lecDispatcher):
        pass

    def doDeleteTask(self, lecDispatcher):
        pass

class ProblemBuilder(LectureBuilder):
    def __init__(self, prob):
        LectureBuilder.__init__(self, prob)

    def getLecture(self):
        return self.MainQuery.contest.lecture

    def doMigrateTask(self, lecDispatcher):
        lecDispatcher.migrateProblem(self.MainQuery)

    def doDeleteTask(self, lecDispatcher):
        lecDispatcher.deleteProblem(self.MainQuery)

class ContestBuilder(LectureBuilder):
    def __init__(self, cont):
        LectureBuilder.__init__(self, cont)

    def getLecture(self):
        return self.MainQuery.lecture

    def doMigrateTask(self, lecDispatcher):
        lecDispatcher.migrateContest(self.MainQuery)

    def doDeleteTask(self, lecDispatcher):
        lecDispatcher.deleteContest(self.MainQuery)

class UserBuilder(LectureBuilder):
    def __init__(self, cont):
        LectureBuilder.__init__(self, cont)

    def getLecture(self):
        pass

    def doMigrateTask(self, lecDispatcher):
        pass

    def doDeleteTask(self, lecDispatcher):
        pass

    def buildLecturebyUser(self, user):
        try:
            lectures = signup_class.objects.filter(isallow=True, user=user).select_related('lecture').order_by('lecture')
        except Exception as e:
            print("exception", e)
        self.buildLecture(lectures)