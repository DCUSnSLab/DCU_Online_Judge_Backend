from problem.models import Problem
from contest.models import Contest
from submission.models import Submission, JudgeStatus
from lecture.models import Lecture, signup_class

class DataType(object):
    POINT = "point"
    SCORE = "score"
    NUMOFSOLVEDCONTENTS = 'numofSolvedContent'
    NUMOFSUBCONTENTS = 'numofSubmitContent'
    NUMOFCONTENTS = "numofcontents"
    AVERAGE = "average"

    NUMOFTOTALSOLVEDPROBLEMS = 'numofTotalSolvedProblems'
    NUMOFTOTALSUBPROBLEMS = 'numofTotalSubmitProblems'
    NUMOFTOTALPROBLEMS = 'numOfTotalProblems'
    TOTALAVERAGE = 'totalAverage'
    ISSUBMITTED = 'isSubmitted'
    ISPASSED = 'isPassed'
    ISVISIBLE = 'isVisible'

    numericTypeList = [POINT, SCORE, NUMOFCONTENTS, AVERAGE, NUMOFTOTALPROBLEMS, TOTALAVERAGE
        , NUMOFSUBCONTENTS, NUMOFTOTALSUBPROBLEMS, NUMOFSOLVEDCONTENTS, NUMOFTOTALSOLVEDPROBLEMS]
    booleanTypeList = [ISSUBMITTED, ISPASSED, ISVISIBLE]
    RefreshList = [POINT, SCORE, NUMOFCONTENTS, NUMOFTOTALPROBLEMS
        , NUMOFSUBCONTENTS, NUMOFTOTALSUBPROBLEMS, NUMOFSOLVEDCONTENTS, NUMOFTOTALSOLVEDPROBLEMS]
    ScoreBoardClearList = [SCORE, AVERAGE, TOTALAVERAGE, ISSUBMITTED, ISPASSED, NUMOFSUBCONTENTS
        , NUMOFTOTALSUBPROBLEMS, NUMOFSOLVEDCONTENTS, NUMOFTOTALSOLVEDPROBLEMS]

class ContestType(object):
    PRACTICE = "실습"
    ASSIGN = "과제"
    cTypeList = [PRACTICE, ASSIGN]

class Information:
    def __init__(self):
        self.data = dict()
        self.initData()

    def initData(self):
        for dtype in DataType.numericTypeList:
            self.data[dtype] = 0

        for dtype in DataType.booleanTypeList:
            self.data[dtype] = 0

    def reCalInfo(self, pinfo):
        for dtype in DataType.RefreshList:
            self.data[dtype] += pinfo.data[dtype]

        self.data[DataType.AVERAGE] = self.calAverage(self.data[DataType.SCORE], self.data[DataType.NUMOFCONTENTS])
        self.data[DataType.TOTALAVERAGE] = self.calAverage(self.data[DataType.SCORE], self.data[DataType.NUMOFTOTALPROBLEMS])

    def calAverage(self, sum, cnt):
        average = 0
        if cnt != 0:
            average = sum / cnt;
        else:
            average = 0
        return average

    def cleanForScoreboard(self):
        for dtype in DataType.ScoreBoardClearList:
            if str(type(self.data[dtype])) == "<class 'bool'>":
                self.data[dtype] = False
            else:
                self.data[dtype] = 0

class LectureAnalysis:
    id = -1
    title = ""

    def __init__(self):
        self.Info = Information()
        self.contAnalysis = dict()
        for ctype in ContestType.cTypeList:
            self.contAnalysis[ctype] = ContestAnalysis(self)


    def migrateProblem(self, problem):
        contest = problem.contest
        ctype = self.typeSelector(contest.lecture_contest_type)
        self.contAnalysis[ctype].migrateProblem(problem)

        # self.contests[cid].addProblem(problem)
        #
        # if problem.visible is True:
        #     self.totalscore += problem.total_score
        #     self.numofProblems += 1

    def reCalInfo(self, cainfo):
        self.Info.reCalInfo(cainfo)
        
    def typeSelector(self, dbtype):
        if dbtype == ContestType.ASSIGN:
            return ContestType.ASSIGN
        elif dbtype == ContestType.PRACTICE:
            return ContestType.PRACTICE
        else:
            return None

    def associateSubmission(self, submission):
        contest = submission.contest
        if contest is not None:
            ctype = self.typeSelector(contest.lecture_contest_type)
            if ctype is not None:
                self.contAnalysis[ctype].associateSubmission(submission)

    def cleanDataForScorebard(self):
        self.Info.cleanForScoreboard()
        for ca in self.contAnalysis.values():
            ca.cleanDataForScorebard()

class ContestAnalysis:

    resLecture = None
    
    def __init__(self, resLecture):
        self.Info = Information()
        self.contests = dict()
        self.resLecture = resLecture

    def migrateProblem(self, problem):
        contest = problem.contest
        cid = contest.id
        resCont = None
        if cid not in self.contests:
            resCont = self.addContest(ResContest(contest, self), cid)
            print("Add Contest :",resCont.id,resCont.title)
        else:
            resCont = self.contests[cid]

        resCont.migrateproblem(problem)

    def reCalInfo(self, cinfo):
        self.Info.reCalInfo(cinfo)
        self.resLecture.reCalInfo(cinfo)

    def addContest(self, resCont, cid):
        self.contests[cid] = resCont
        return resCont

    def associateSubmission(self, submission):
        cid = submission.contest.id
        selectedContest = self.contests[cid]
        if selectedContest is not None:
            selectedContest.associateSubmission(submission)

    def cleanDataForScorebard(self):
        self.Info.cleanForScoreboard()
        for co in self.contests.values():
            co.cleanDataForScorebard()

class ResContest:
    Id = -1
    title = ""
    IS_NewContest = False

    def __init__(self, contest, contA):
        self.contAnalysis = contA
        self.Info = Information()
        self.problems = dict()
        self.myContest = contest
        self.id = contest.id
        self.title = contest.title
        self.contestType = self.typeSelector(contest.lecture_contest_type)
        self.IS_NewContest = True

        self.Info.data[DataType.ISVISIBLE] = contest.visible

    def migrateproblem(self, problem):
        inprob = RefProblem(problem, self)
        self.problems[inprob.Id] = inprob

    def reCalInfo(self, pinfo):
        if self.Info.data[DataType.ISVISIBLE] is True:
            self.Info.reCalInfo(pinfo)

            if self.IS_NewContest is True:
                pinfo.data[DataType.NUMOFCONTENTS] = 1
                self.IS_NewContest = False
            else:
                pinfo.data[DataType.NUMOFCONTENTS] = 0

            #if all problems of contest have been solved, please count solved contest as below

            self.contAnalysis.reCalInfo(pinfo)

    def typeSelector(self, dbtype):
        if dbtype == ContestType.ASSIGN:
            return ContestType.ASSIGN
        else:
            return ContestType.PRACTICE

    def associateSubmission(self, submission):
        pid = submission.problem.id
        subprob = self.problems[pid]
        if subprob is not None:
            subprob.associateSubmission(submission)

    def cleanDataForScorebard(self):
        self.Info.cleanForScoreboard()
        for po in self.problems.values():
            po.cleanDataForScorebard()

class RefProblem():
    Id = -1

    def __init__(self, problem, cont):
        self.Id = problem.id
        self.pcontest = cont
        self.Info = Information()
        self.myproblem = None
        self.mysubmission = None
        self.migrateProblem(problem)

    def migrateProblem(self, problem):
        self.myproblem = problem
        self.Info.data[DataType.POINT] = problem.total_score
        self.Info.data[DataType.ISVISIBLE] = problem.visible
        self.Info.data[DataType.NUMOFCONTENTS] = 1
        self.Info.data[DataType.NUMOFTOTALPROBLEMS] = 1
        self.pcontest.reCalInfo(self.Info)

    def associateSubmission(self, submission):
        self.mysubmission = submission

        Json = submission.info

        if Json:  # 해당 사용자의 submit 이력이 있는 경우 (Submission에 사용자의 id값이 포함된 값이 있는 경우)
            for jsondata in Json['data']:
                self.Info.data[DataType.SCORE] += jsondata['score']

        if submission.result == JudgeStatus.ACCEPTED:
            self.Info.data[DataType.ISPASSED] = True
            self.Info.data[DataType.NUMOFSOLVEDCONTENTS] = 1
            self.Info.data[DataType.NUMOFTOTALSOLVEDPROBLEMS] = 1

        self.Info.data[DataType.NUMOFTOTALSUBPROBLEMS] = 1
        self.Info.data[DataType.NUMOFSUBCONTENTS] = 1

        cinfo = self.cloneInfoForSubmit(self.Info)
        self.pcontest.reCalInfo(cinfo)

    def cloneInfoForSubmit(self, origin):
        info = Information()
        info.data[DataType.ISPASSED] = origin.data[DataType.ISPASSED]
        info.data[DataType.ISVISIBLE] = origin.data[DataType.ISVISIBLE]
        info.data[DataType.SCORE] = origin.data[DataType.SCORE]
        info.data[DataType.NUMOFTOTALSUBPROBLEMS] = origin.data[DataType.NUMOFTOTALSUBPROBLEMS]
        info.data[DataType.NUMOFSUBCONTENTS] = origin.data[DataType.NUMOFSUBCONTENTS]
        info.data[DataType.NUMOFSOLVEDCONTENTS] = origin.data[DataType.NUMOFSOLVEDCONTENTS]
        info.data[DataType.NUMOFTOTALSOLVEDPROBLEMS] = origin.data[DataType.NUMOFTOTALSOLVEDPROBLEMS]
        return info

    def cleanDataForScorebard(self):
        self.Info.cleanForScoreboard()
