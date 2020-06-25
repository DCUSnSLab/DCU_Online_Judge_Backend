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
    # RefreshList = [POINT, SCORE, NUMOFCONTENTS, NUMOFTOTALPROBLEMS
    #     , NUMOFSUBCONTENTS, NUMOFTOTALSUBPROBLEMS, NUMOFSOLVEDCONTENTS, NUMOFTOTALSOLVEDPROBLEMS]
    ScoreBoardClearList = [SCORE, AVERAGE, PROGRESS, ISSUBMITTED, ISPASSED, NUMOFSUBCONTENTS
        , NUMOFTOTALSUBPROBLEMS, NUMOFSOLVEDCONTENTS, NUMOFTOTALSOLVEDPROBLEMS]

    #for Calculation
    MigrationList = [NUMOFTOTALPROBLEMS, POINT]
    AssociationList = [NUMOFTOTALSOLVEDPROBLEMS, NUMOFTOTALSUBPROBLEMS, SCORE]

    MigrationClearList = [NUMOFCONTENTS, NUMOFTOTALPROBLEMS, POINT]
    AssociationClearList = [NUMOFSOLVEDCONTENTS, NUMOFSUBCONTENTS, NUMOFTOTALSOLVEDPROBLEMS, NUMOFTOTALSUBPROBLEMS, SCORE, ISSUBMITTED, ISPASSED]

class ContestType(object):
    PRACTICE = "실습"
    ASSIGN = "과제"
    CONTEST = "대회"
    cTypeList = [PRACTICE, ASSIGN, CONTEST]

#Lectuer Dictionary Keys for data exchanging from class to dictionary
class LectureDictionaryKeys:
    INFO = 'Info'
    CONTESTANALYSIS = 'ContestAnalysis'
    CONTESTS = 'contests'
    PROBLEMS = 'problems'
    CONTEST_TITLE = 'ctitle'
    CONTEST_TYPE = 'ctype'
    CONTEST_SOLVE_CNT = 'csolvecnt'
    CONTEST_IS_SUBMIT = 'cissubmit'

class Information:
    def __init__(self):
        self.data = dict()
        self.initData()

    def initData(self):
        self.cleanDatasbyList(DataType.dataTypeList)

    def reCalInfo(self, contents, isMigrate, isAssociate):
        #Clean Data
        if isMigrate:
            self.cleanDatasbyList(DataType.MigrationClearList)
        if isAssociate:
            self.cleanDatasbyList(DataType.AssociationClearList)

        #Re-calculate data
        solveCheck = True
        for cont in contents.values():
            if not cont.Info.data[DataType.ISVISIBLE]:
                continue

            if isMigrate:
                for dtype in DataType.MigrationList:
                    self.data[dtype] += cont.Info.data[dtype]

                self.data[DataType.NUMOFCONTENTS] += 1

            if isAssociate:
                for dtype in DataType.AssociationList:
                    self.data[dtype] += cont.Info.data[dtype]

                if cont.Info.data[DataType.ISSUBMITTED]:
                    self.data[DataType.NUMOFSUBCONTENTS] += 1
                    self.data[DataType.ISSUBMITTED] = True

                if cont.Info.data[DataType.ISPASSED]:
                    self.data[DataType.NUMOFSOLVEDCONTENTS] += 1
                else:
                    solveCheck = False

            #round(self.totalscore * 100 / self.LectureInfo.totalscore, 2)
            self.data[DataType.AVERAGE] = self.calAverage(self.data[DataType.SCORE], self.data[DataType.POINT])

            #cal progress
            if self.data[DataType.NUMOFTOTALPROBLEMS] != 0:
                self.data[DataType.PROGRESS] = round(self.data[DataType.NUMOFTOTALSUBPROBLEMS] / self.data[DataType.NUMOFTOTALPROBLEMS] * 100, 2)

        if isAssociate and solveCheck:
            self.data[DataType.ISPASSED] = True

    def calAverage(self, sum, totalScore):
        average = 0
        if totalScore != 0:
            average = round(sum * 100 / totalScore, 2)
        else:
            average = 0
        return average

    def cleanForScoreboard(self):
        self.cleanDatasbyList(DataType.ScoreBoardClearList)

    def cleanDatabyList(self, dtype):
        if str(type(self.data[dtype])) == "<class 'bool'>":
            self.data[dtype] = False
        else:
            self.data[dtype] = 0

    def cleanDatasbyList(self, dTypeList):
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

class Content:
    id = -1
    title = ""
    def __init__(self):
        self.Info = Information()

class LectureAnalysis(Content):

    def __init__(self):
        Content.__init__(self)
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

    def deleteProblem(self, problem):
        contest = problem.contest
        ctype = self.typeSelector(contest.lecture_contest_type)
        self.contAnalysis[ctype].deleteProblem(problem)

    def migrateContest(self, contest):
        ctype = self.typeSelector(contest.lecture_contest_type)
        self.contAnalysis[ctype].migrateContest(contest)

    def deleteContest(self, contest):
        ctype = self.typeSelector(contest.lecture_contest_type)
        self.contAnalysis[ctype].deleteContest(contest)

    def reCalInfo(self, isMigrate, isAssociate):
        self.Info.reCalInfo(self.contAnalysis, isMigrate, isAssociate)
        
    def typeSelector(self, dbtype):
        if dbtype == ContestType.ASSIGN:
            return ContestType.ASSIGN
        elif dbtype == ContestType.PRACTICE:
            return ContestType.PRACTICE
        elif dbtype== ContestType.CONTEST:
            return ContestType.CONTEST
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

class lecDispatcher(LectureAnalysis):
    def __init__(self):
        LectureAnalysis.__init__(self)
        self.id = 0

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
                contdict[LectureDictionaryKeys.CONTEST_IS_SUBMIT] = cont.isSubmitted
                contdict[LectureDictionaryKeys.PROBLEMS] = probsdict
                contsdict[contkey] = contdict

            CAdict = dict()
            CAdict[LectureDictionaryKeys.INFO] = CA.Info.data
            CAdict[LectureDictionaryKeys.CONTESTS] = contsdict
            CASdict[ckey] = CAdict

        ldict[LectureDictionaryKeys.CONTESTANALYSIS] = CASdict

        return ldict

    def fromDict(self, dicdata):
        if dicdata is None or len(dicdata) == 0:
            return

        self.Info.data = dicdata[LectureDictionaryKeys.INFO]

        for contA in dicdata[LectureDictionaryKeys.CONTESTANALYSIS].keys():
            dicContA = dicdata[LectureDictionaryKeys.CONTESTANALYSIS][contA]
            inContA = self.contAnalysis[contA]
            inContA.Info.data = dicContA[LectureDictionaryKeys.INFO]
            inContA.migrateDictionary(dicContA)

class ContestAnalysis (Content):

    resLecture = None
    
    def __init__(self, resLecture):
        Content.__init__(self)
        self.Info.data[DataType.ISVISIBLE] = True
        self.contests = dict()
        self.resLecture = resLecture

    def migrateProblem(self, problem):
        contest = problem.contest
        cid = contest.id
        resCont = None
        if cid not in self.contests:
            resCont = self.addContest(ResContest(contA=self, contest=contest), cid)
            #print("Add Contest :",resCont.id,resCont.title)
        else:
            resCont = self.contests[cid]

        resCont.migrateproblem(problem)

    def deleteProblem(self, problem):
        contest = problem.contest
        cid = contest.id
        resCont = None
        if cid in self.contests:
            resCont = self.contests[cid]
            resCont.deleteProblem(problem)

    def migrateContest(self, contest):
        cid = contest.id
        if cid in self.contests:
            self.contests[cid].migrateContest(contest)

    def deleteContest(self, contest):
        cid = contest.id
        if cid in self.contests:
            self.contests.pop(cid)
            self.reCalInfo(True, True)

    def migrateDictionary(self, dicData):
        for contestkey in dicData['contests'].keys():
            contDict = dicData['contests'][contestkey]
            cdict = {'id':contestkey,
                     'title':contDict[LectureDictionaryKeys.CONTEST_TITLE],
                     'type':contDict[LectureDictionaryKeys.CONTEST_TYPE],
                     'scnt':contDict[LectureDictionaryKeys.CONTEST_SOLVE_CNT],
                     'issubmit':contDict[LectureDictionaryKeys.CONTEST_IS_SUBMIT],
                     'Info':contDict['Info']}
            resCont = self.addContest(ResContest(contA=self, contDict=cdict), int(contestkey))
            resCont.migrateDictionary(contDict)

    def reCalInfo(self, isMigrate, isAssociate):
        self.Info.reCalInfo(self.contests, isMigrate, isAssociate)
        self.resLecture.reCalInfo(isMigrate, isAssociate)

    def addContest(self, resCont, cid):
        self.contests[cid] = resCont
        return resCont

    def associateSubmission(self, submission):
        cid = submission.contest.id
        try:
            selectedContest = self.contests[cid]
        except KeyError:
            selectedContest = self.contests[str(cid)]
        except Exception as e:
            print('Exception ',e)

        if selectedContest is not None:
            selectedContest.associateSubmission(submission)

    def cleanDataForScorebard(self):
        self.Info.cleanForScoreboard()
        for co in self.contests.values():
            co.cleanDataForScorebard()

class ResContest (Content):

    contestType = ""
    IS_NewContest = False
    solveCount = 0
    isSubmitted = False

    def __init__(self, contA, contest=None, contDict=None):
        Content.__init__(self)
        self.contAnalysis = contA
        self.problems = dict()

        if contest is not None:
            self.id = contest.id
            self.title = contest.title
            self.contestType = self.typeSelector(contest.lecture_contest_type)
            self.Info.data[DataType.ISVISIBLE] = contest.visible
            self.IS_NewContest = True
        else:
            self.id = contDict['id']
            self.title = contDict['title']
            self.contestType = contDict['type']
            self.Info.data = contDict['Info']
            self.solveCount = contDict['scnt']
            self.isSubmitted = contDict['issubmit']


    def migrateproblem(self, problem):
        if problem.visible is True:
            pid = problem.id
            if pid not in self.problems:
                inprob = RefProblem(cont=self, problem=problem)
                self.problems[inprob.id] = inprob

                self.solveCount += 1
            else:
                inprob = self.problems[pid]

            inprob.migrateProblem(problem)

    def deleteProblem(self, problem):
        pid = problem.id
        if pid in self.problems:
            self.problems.pop(pid)
            self.reCalInfo(isMigrate=True, isAssociate=True)

    def migrateContest(self, contest):
        self.title = contest.title
        self.contestType = self.typeSelector(contest.lecture_contest_type)
        self.Info.data[DataType.ISVISIBLE] = contest.visible
        self.reCalInfo(isMigrate=True, isAssociate=False)

    def migrateDictionary(self, dicData):
        for probkey in dicData[LectureDictionaryKeys.PROBLEMS].keys():
            problem = dicData[LectureDictionaryKeys.PROBLEMS][probkey]
            probDict = {'id':probkey, 'Info':problem[LectureDictionaryKeys.INFO]}
            self.problems[int(probkey)] = RefProblem(cont=self, probDict=probDict)

    def reCalInfo(self, isMigrate, isAssociate):
        if self.Info.data[DataType.ISVISIBLE] is True:
            self.Info.reCalInfo(self.problems, isMigrate, isAssociate)

            #self.checkContestStatus()
            self.contAnalysis.reCalInfo(isMigrate, isAssociate)

            #if all problems of contest have been solved, please count solved contest as below
            # self.checkContestStatus(pinfo)
            #
            #
            # self.contAnalysis.reCalInfo(pinfo)

    def typeSelector(self, dbtype):
        if dbtype == ContestType.ASSIGN:
            return ContestType.ASSIGN
        else:
            return ContestType.PRACTICE

    def associateSubmission(self, submission):
        pid = submission.problem.id
        try:
            subprob = self.problems[pid]
        except KeyError:
            subprob = self.problems[str(pid)]
        except Exception as e:
            print("Exception ",e)
        if subprob is not None:
            subprob.associateSubmission(submission)

    def cleanDataForScorebard(self):
        self.isSubmitted = False
        self.solveCount = len(self.problems)
        self.Info.cleanForScoreboard()
        for po in self.problems.values():
            po.cleanDataForScorebard()

class RefProblem(Content):

    def __init__(self, cont, problem=None, probDict=None):
        Content.__init__(self)
        self.pcontest = cont
        self.Info = Information()
        self.mysubmission = None

        if problem is not None:
            self.id = problem.id
        else:
            self.id = probDict['id']
            self.Info.data = probDict['Info']

    def migrateProblem(self, problem):
        self.title = problem.title
        self.Info.data[DataType.POINT] = problem.total_score
        self.Info.data[DataType.ISVISIBLE] = problem.visible
        self.Info.data[DataType.NUMOFCONTENTS] = 1
        self.Info.data[DataType.NUMOFTOTALPROBLEMS] = 1

        self.pcontest.reCalInfo(isMigrate=True, isAssociate=False)

    def associateSubmission(self, submission):
        self.mysubmission = submission

        # Passed Submitdata testtddd
        if submission.result == JudgeStatus.ACCEPTED or submission.result == JudgeStatus.PARTIALLY_ACCEPTED:
            Json = submission.info
            self.Info.data[DataType.SCORE] = 0
            if Json:
                for jsondata in Json['data']:
                    self.Info.data[DataType.SCORE] += jsondata['score']

            self.Info.data[DataType.ISPASSED] = True
            self.Info.data[DataType.NUMOFSOLVEDCONTENTS] = 1
            self.Info.data[DataType.NUMOFTOTALSOLVEDPROBLEMS] = 1
        #passed -> fail
        else:
            self.Info.data[DataType.SCORE] = 0
            self.Info.data[DataType.ISPASSED] = False
            self.Info.data[DataType.NUMOFSOLVEDCONTENTS] = 0
            self.Info.data[DataType.NUMOFTOTALSOLVEDPROBLEMS] = 0

        if not self.Info.data[DataType.ISSUBMITTED]:
            self.Info.data[DataType.NUMOFTOTALSUBPROBLEMS] = 1
            self.Info.data[DataType.NUMOFSUBCONTENTS] = 1
            self.Info.data[DataType.ISSUBMITTED] = True

        self.pcontest.reCalInfo(isMigrate=False, isAssociate=True)

    def cleanDataForScorebard(self):
        self.Info.cleanForScoreboard()
