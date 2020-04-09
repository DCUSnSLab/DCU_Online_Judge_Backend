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

    NUMOFTOTALSOLVEDPROBLEMS = 'numofTotalSolvedProblems'
    NUMOFTOTALSUBPROBLEMS = 'numofTotalSubmitProblems'
    NUMOFTOTALPROBLEMS = 'numOfTotalProblems'

    AVERAGE = "average"

    PROGRESS = "progress"

    ISSUBMITTED = 'isSubmitted'
    ISPASSED = 'isPassed'
    ISVISIBLE = 'isVisible'

    #Initialization
    dataTypeList = [POINT, SCORE, NUMOFCONTENTS, AVERAGE, PROGRESS, NUMOFTOTALPROBLEMS
        , NUMOFSUBCONTENTS, NUMOFTOTALSUBPROBLEMS, NUMOFSOLVEDCONTENTS, NUMOFTOTALSOLVEDPROBLEMS, ISSUBMITTED, ISPASSED, ISVISIBLE]
    # numericTypeList = [POINT, SCORE, NUMOFCONTENTS, AVERAGE, PROGRESS, NUMOFTOTALPROBLEMS
    #     , NUMOFSUBCONTENTS, NUMOFTOTALSUBPROBLEMS, NUMOFSOLVEDCONTENTS, NUMOFTOTALSOLVEDPROBLEMS]
    booleanTypeList = [ISSUBMITTED, ISPASSED, ISVISIBLE]

    #Conditional
    RefreshList = [POINT, SCORE, NUMOFCONTENTS, NUMOFTOTALPROBLEMS
        , NUMOFSUBCONTENTS, NUMOFTOTALSUBPROBLEMS, NUMOFSOLVEDCONTENTS, NUMOFTOTALSOLVEDPROBLEMS]
    ScoreBoardClearList = [SCORE, AVERAGE, PROGRESS, ISSUBMITTED, ISPASSED, NUMOFSUBCONTENTS
        , NUMOFTOTALSUBPROBLEMS, NUMOFSOLVEDCONTENTS, NUMOFTOTALSOLVEDPROBLEMS]

    #for Problem Clean
    problemSubmitExceptList = [POINT, NUMOFCONTENTS, AVERAGE, PROGRESS, NUMOFTOTALPROBLEMS]

class ContestType(object):
    PRACTICE = "실습"
    ASSIGN = "과제"
    cTypeList = [PRACTICE, ASSIGN]

class Information:
    def __init__(self):
        self.data = dict()
        self.initData()

    def initData(self):
        self.cleanDatabyList(DataType.dataTypeList)

    def reCalInfo(self, pinfo):
        for dtype in DataType.RefreshList:
            self.data[dtype] += pinfo.data[dtype]
        #round(self.totalscore * 100 / self.LectureInfo.totalscore, 2)
        self.data[DataType.AVERAGE] = self.calAverage(self.data[DataType.SCORE], self.data[DataType.POINT])

        #cal progress
        if self.data[DataType.NUMOFTOTALPROBLEMS] != 0:
            self.data[DataType.PROGRESS] = round(self.data[DataType.NUMOFTOTALSUBPROBLEMS] / self.data[DataType.NUMOFTOTALPROBLEMS] * 100, 2)

    def calAverage(self, sum, totalScore):
        average = 0
        if totalScore != 0:
            average = round(sum * 100 / totalScore, 2)
        else:
            average = 0
        return average

    def cleanForScoreboard(self):
        self.cleanDatabyList(DataType.ScoreBoardClearList)

    def cleanDatabyList(self, dTypeList):
        if len(self.data) == 0:
            for dtype in dTypeList:
                self.data[dtype] = 0
            for dtype in DataType.booleanTypeList:
                self.data[dtype] = False
        else:
            for dtype in dTypeList:
                if str(type(self.data[dtype])) == "<class 'bool'>":
                    self.data[dtype] = False
                else:
                    self.data[dtype] = 0

    def clone(self):
        cinfo = Information()
        for dtype in DataType.dataTypeList:
            cinfo.data[dtype] = self.data[dtype]

        return cinfo

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

    def toDict(self):
        ldict = dict()
        ldict[LectureDictionaryKeys.INFO] = self.Info.data

        CASdict = dict()
        for ckey in self.contAnalysis.keys():
            CA = self.contAnalysis[ckey]
            contsdict = dict()
            for contkey in CA.contests.keys():
                cont = CA.contests[contkey]
                probsdict = dict()
                for pkey in cont.problems.keys():
                    probdict = dict()
                    probs = cont.problems[pkey]
                    probdict[LectureDictionaryKeys.INFO] = probs.Info.data
                    probsdict[pkey] = probdict

                contdict = dict()
                contdict[LectureDictionaryKeys.CONTEST_TITLE] = cont.title
                contdict[LectureDictionaryKeys.INFO] = cont.Info.data
                contdict[LectureDictionaryKeys.CONTEST_TYPE] = cont.contestType
                contdict[LectureDictionaryKeys.CONTEST_SOLVE_CNT] = cont.solveCount
                contdict[LectureDictionaryKeys.PROBLEMS] = probsdict
                contsdict[contkey] = contdict

            CAdict = dict()
            CAdict[LectureDictionaryKeys.INFO] = CA.Info.data
            CAdict[LectureDictionaryKeys.CONTESTS] = contsdict
            CASdict[ckey] = CAdict

        ldict[LectureDictionaryKeys.CONTESTANALYSIS] = CASdict

        return ldict

    def fromDict(self, dicdata):
        self.Info.data = dicdata[LectureDictionaryKeys.INFO]

        for contA in dicdata[LectureDictionaryKeys.CONTESTANALYSIS].keys():
            dicContA = dicdata[LectureDictionaryKeys.CONTESTANALYSIS][contA]
            inContA = self.contAnalysis[contA]
            inContA.Info.data = dicContA[LectureDictionaryKeys.INFO]
            inContA.migrateDictionary(dicContA)

class LectureDictionaryKeys:
    INFO = 'Info'
    CONTESTANALYSIS = 'ContestAnalysis'
    CONTESTS = 'contests'
    PROBLEMS = 'problems'
    CONTEST_TITLE = 'ctitle'
    CONTEST_TYPE = 'ctype'
    CONTEST_SOLVE_CNT = 'csolvecnt'


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
            resCont = self.addContest(ResContest(contA=self, contest=contest), cid)
            print("Add Contest :",resCont.id,resCont.title)
        else:
            resCont = self.contests[cid]

        resCont.migrateproblem(problem)

    def migrateDictionary(self, dicData):
        for contestkey in dicData['contests'].keys():
            contDict = dicData['contests'][contestkey]
            cdict = {'id':contestkey,
                     'title':contDict[LectureDictionaryKeys.CONTEST_TITLE],
                     'type':contDict[LectureDictionaryKeys.CONTEST_TYPE],
                     'scnt':contDict[LectureDictionaryKeys.CONTEST_SOLVE_CNT],
                     'Info':contDict['Info']}
            resCont = self.addContest(ResContest(contA=self, contDict=cdict), contestkey)
            resCont.migrateDictionary(contDict)

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
    contestType = ""
    IS_NewContest = False
    solveCount = 0
    isSubmitted = False

    def __init__(self, contA, contest=None, contDict=None):
        self.contAnalysis = contA
        self.Info = Information()
        self.problems = dict()
        self.IS_NewContest = True

        if contest is not None:
            self.id = contest.id
            self.title = contest.title
            self.contestType = self.typeSelector(contest.lecture_contest_type)
            self.Info.data[DataType.ISVISIBLE] = contest.visible
        else:
            self.id = contDict['id']
            self.title = contDict['title']
            self.contestType = contDict['type']
            self.Info.data = contDict['Info']
            self.solveCount = contDict['scnt']



    def migrateproblem(self, problem):
        if problem.visible is True:
            inprob = RefProblem(cont=self, problem=problem)
            self.problems[inprob.Id] = inprob
            self.solveCount += 1

    def migrateDictionary(self, dicData):
        for probkey in dicData[LectureDictionaryKeys.PROBLEMS].keys():
            problem = dicData[LectureDictionaryKeys.PROBLEMS][probkey]
            probDict = {'id':probkey, 'Info':problem[LectureDictionaryKeys.INFO]}
            self.problems[probkey] = RefProblem(cont=self, probDict=probDict)

    def reCalInfo(self, pinfo):
        if self.Info.data[DataType.ISVISIBLE] is True:
            self.Info.reCalInfo(pinfo)

            if self.IS_NewContest is True:
                pinfo.data[DataType.NUMOFCONTENTS] = 1
                self.IS_NewContest = False
            else:
                pinfo.data[DataType.NUMOFCONTENTS] = 0

            #if all problems of contest have been solved, please count solved contest as below
            self.checkContestStatus(pinfo)


            self.contAnalysis.reCalInfo(pinfo)

    def checkContestStatus(self, pinfo):
        pinfo.data[DataType.NUMOFSUBCONTENTS] = 0
        pinfo.data[DataType.NUMOFSOLVEDCONTENTS] = 0

        #Submit Check
        if pinfo.data[DataType.ISSUBMITTED] is True and self.isSubmitted is False:
            pinfo.data[DataType.NUMOFSUBCONTENTS] = 1
            self.isSubmitted = True

        #Solved Check
        if pinfo.data[DataType.ISPASSED] is True:
            self.solveCount -= 1

        if self.solveCount == 0:
            pinfo.data[DataType.NUMOFSOLVEDCONTENTS] = 1

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
        self.isSubmitted = False
        self.solveCount = len(self.problems)
        self.Info.cleanForScoreboard()
        for po in self.problems.values():
            po.cleanDataForScorebard()

class RefProblem():
    Id = -1

    def __init__(self, cont, problem=None, probDict=None):
        self.pcontest = cont
        self.Info = Information()
        self.mysubmission = None

        if problem is not None:
            self.Id = problem.id
            self.migrateProblem(problem)
        else:
            self.Id = probDict['id']
            self.Info.data = probDict['Info']

    def migrateProblem(self, problem):
        self.Info.data[DataType.POINT] = problem.total_score
        self.Info.data[DataType.ISVISIBLE] = problem.visible
        self.Info.data[DataType.NUMOFCONTENTS] = 1
        self.Info.data[DataType.NUMOFTOTALPROBLEMS] = 1
        cinfo = self.Info.clone()
        self.pcontest.reCalInfo(cinfo)

    def associateSubmission(self, submission):
        self.mysubmission = submission

        Json = submission.info

        if Json:
            for jsondata in Json['data']:
                self.Info.data[DataType.SCORE] += jsondata['score']

        if submission.result == JudgeStatus.ACCEPTED:
            self.Info.data[DataType.ISPASSED] = True
            self.Info.data[DataType.NUMOFSOLVEDCONTENTS] = 1
            self.Info.data[DataType.NUMOFTOTALSOLVEDPROBLEMS] = 1

        self.Info.data[DataType.NUMOFTOTALSUBPROBLEMS] = 1
        self.Info.data[DataType.NUMOFSUBCONTENTS] = 1
        self.Info.data[DataType.ISSUBMITTED] = True
        #cinfo = self.cloneInfoForSubmit(self.Info)
        cinfo = self.Info.clone()
        self.CleanforSubmit(cinfo)
        self.pcontest.reCalInfo(cinfo)

    #need to modify
    def CleanforSubmit(self, origin):
        origin.cleanDatabyList(DataType.problemSubmitExceptList)

    def cleanDataForScorebard(self):
        self.Info.cleanForScoreboard()
