from problem.models import Problem
from contest.models import Contest
from submission.models import Submission, JudgeStatus
from lecture.models import Lecture, signup_class
import copy

class DataType(object):
    '''
        POINT : 출제된 문제들의 총점
        SCORE : 사용자가 획득한 총 점수
        NUMOFCONTENTS : Info 기준 (과제, 실습, 대회) / 과제, 실습, 대회 Info 기준 ( 각 Contest의 개수 ) / Contest 내부 ( 각 Contest 별 Problem의 개수)
        AVERAGE : 각 문제 별 100점 만점 환산 후 평균
        PROGRESS : 전제 문제의 진행 정도를 백분율로 진행
        NUMOFTOTALPROBLEMS : 전체 문제(Problem) 개수
        NUMOFSUBCONTENTS : 제출하기를 1회 이상 누른 Contest의 총 개수
        NUMOFTOTALSUBPROBLEMS : 제출하기를 1회 이상 누른 문제의 총 개수
        NUMOFSOLVEDCONTENTS : 정답/부분정답을 통해 점수를 획득한 Contest의 개수
        NUMOFTOTALSOLVEDPROBLEMS : 정답/부분정답을 통해 점수를 획득한 문제(Problem)의 개수
        ISSUBMITTED : 1회 이상 제출버튼 클릭 여부
        ISPASSED : 정답/부분정답을 통해 점수를 획득한 경우
        ISVISIBLE : Contest / Problem 공개 여부
    '''
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

    # Initialization
    dataTypeList = [POINT, SCORE, NUMOFCONTENTS, AVERAGE, PROGRESS, NUMOFTOTALPROBLEMS
        , NUMOFSUBCONTENTS, NUMOFTOTALSUBPROBLEMS, NUMOFSOLVEDCONTENTS, NUMOFTOTALSOLVEDPROBLEMS, ISSUBMITTED, ISPASSED,
                    ISVISIBLE]
    # numericTypeList = [POINT, SCORE, NUMOFCONTENTS, AVERAGE, PROGRESS, NUMOFTOTALPROBLEMS
    #     , NUMOFSUBCONTENTS, NUMOFTOTALSUBPROBLEMS, NUMOFSOLVEDCONTENTS, NUMOFTOTALSOLVEDPROBLEMS]

    # booleanType List dict
    booleanTypeList = [ISSUBMITTED, ISPASSED, ISVISIBLE]

    # Conditional
    # RefreshList = [POINT, SCORE, NUMOFCONTENTS, NUMOFTOTALPROBLEMS
    #     , NUMOFSUBCONTENTS, NUMOFTOTALSUBPROBLEMS, NUMOFSOLVEDCONTENTS, NUMOFTOTALSOLVEDPROBLEMS]
    ScoreBoardClearList = [SCORE, AVERAGE, PROGRESS, ISSUBMITTED, ISPASSED, NUMOFSUBCONTENTS
        , NUMOFTOTALSUBPROBLEMS, NUMOFSOLVEDCONTENTS, NUMOFTOTALSOLVEDPROBLEMS]

    # for Calculation
    MigrationList = [NUMOFTOTALPROBLEMS, POINT]
    AssociationList = [NUMOFTOTALSOLVEDPROBLEMS, NUMOFTOTALSUBPROBLEMS, SCORE]

    MigrationClearList = [NUMOFCONTENTS, NUMOFTOTALPROBLEMS, POINT]
    AssociationClearList = [NUMOFSOLVEDCONTENTS, NUMOFSUBCONTENTS, NUMOFTOTALSOLVEDPROBLEMS, NUMOFTOTALSUBPROBLEMS,
                            SCORE, ISSUBMITTED, ISPASSED]


class ContestType(object):
    PRACTICE = "실습"
    ASSIGN = "과제"
    CONTEST = "대회"
    cTypeList = [PRACTICE, ASSIGN, CONTEST]


# Lectuer Dictionary Keys for data exchanging from class to dictionary
class LectureDictionaryKeys:
    '''
    INFO : Dic name
    CONTESTANALYSIS : 실습, 과제, 대회 분류
    CONTESTS = 실습, 과제, 대회 내부 Contest 리스트
    PROBLEMS = 실습, 과제, 대회 내부 Problem 리스트
    CONTEST_TITLE = 실습, 과제, 대회 제목
    CONTEST_TYPE = 실습, 과제, 대회 분류
    CONTEST_SOLVE_CNT = 전체 해결한 문제 개수
    CONTEST_IS_SUBMIT = ????
    '''
    INFO = 'Info'
    CONTESTANALYSIS = 'ContestAnalysis'
    CONTESTS = 'contests'
    PROBLEMS = 'problems'
    CONTEST_TITLE = 'ctitle'
    CONTEST_TYPE = 'ctype'
    CONTEST_SOLVE_CNT = 'csolvecnt'
    CONTEST_IS_SUBMIT = 'cissubmit'

'''
    Information 객체 생성시 가장 처음 동작되는 생성자 (__init__)
    저장되는 data를 dict 타입으로 생성 및 저장 대상이 되는 데이터 타입 전체를 초기화 진행
    @param : X
'''


class Information:

    def __init__(self):
        self.data = dict()
        self.initData()

    '''
        저장되는 데이터 전체를 초기화 진행하기 위해 동작되는 메소드
        @param : X
    '''

    def initData(self):
        self.cleanDatasbyList(DataType.dataTypeList)

    '''
        기존에 저장된 데이터에서 값을 업데이트 및 재 계산을 수행하기 위한 메소드
        멤버 인자로 주어진 isMigrate, isAssociate에 따라 동작이 달라진다.
        @param contents : 현재 업데이트 대상인 Lecture, Contest, Problem
        @param isMigrate : MigrationList 대상의 값을 업데이트 수행한다.
        @param isAssociate : AssociationClearList 대상의 값을 업데이트 수행한다.
    '''

    def reCalInfo(self, contents, isMigrate, isAssociate):
        # Clean Data
        if isMigrate:
            self.cleanDatasbyList(DataType.MigrationClearList)
        if isAssociate:
            self.cleanDatasbyList(DataType.AssociationClearList)

        # Re-calculate data
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

            # round(self.totalscore * 100 / self.LectureInfo.totalscore, 2)
            self.data[DataType.AVERAGE] = self.calAverage(self.data[DataType.SCORE], self.data[DataType.POINT])

            # cal progress
            if self.data[DataType.NUMOFTOTALPROBLEMS] != 0:
                self.data[DataType.PROGRESS] = round(
                    self.data[DataType.NUMOFTOTALSUBPROBLEMS] / self.data[DataType.NUMOFTOTALPROBLEMS] * 100, 2)

        if isAssociate and solveCheck:
            self.data[DataType.ISPASSED] = True

    '''
        학생이 각 problem별 100점 만점 기준으로 전체 평균 계산
        @param sum : self.data[DataType.SCORE]
        @param totalScore : self.data[DataType.POINT]
    '''

    def calAverage(self, sum, totalScore):
        average = 0
        if totalScore != 0:
            average = round(sum * 100 / totalScore, 2)
        else:
            average = 0
        return average

    '''
        사용자가 제출한 점수와 직접적인 연관이 있는 데이터들을 대상으로 초기화 진행
        초기화 대상은 DataType.ScoreBoardClearList임.
        ScoreBoardClearList = [SCORE, AVERAGE, PROGRESS, ISSUBMITTED, ISPASSED, NUMOFSUBCONTENTS, NUMOFTOTALSUBPROBLEMS, NUMOFSOLVEDCONTENTS, NUMOFTOTALSOLVEDPROBLEMS]
    '''

    def cleanForScoreboard(self):
        self.cleanDatasbyList(DataType.ScoreBoardClearList)

    '''
        주어진 특정 value 하나를 대상으로 타입 별 기본 값으로 초기화 진행
        dtype == bool --> False
        dtype == integer --> 0
    '''

    def cleanDatabyList(self, dtype):
        if str(type(self.data[dtype])) == "<class 'bool'>":
            self.data[dtype] = False
        else:
            self.data[dtype] = 0

    '''
        Lecture, Contest, Problem 생성 시 dict에 존재하는 데이터 타입의 값(Json)을 초기화 진행
        정수 기반 동작 value 는 0
        boolean 기반 동작 value 는 False
    '''

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

    '''
        저장된 Lecture, Contest, Problem의 info값을 복사 및 반환하는 함수
    '''

    def clone(self):
        cinfo = Information()
        for dtype in DataType.dataTypeList:
            cinfo.data[dtype] = self.data[dtype]

        return cinfo


'''
    Content(Lecture, Contest, Problem)의 점수 저장 및 계산을 수행하는 Infomation class를 초기 값으로 할당하기 위한 부모 class
    * Todo : Abstract Class로 변형하여 좀 더 가독성 좋게 변경 할 수 있을 듯 함.
    @param : X
'''


class Content:
    id = -1
    title = ""

    def __init__(self):
        self.Info = Information()


'''
    LectureAnalysis Class : 과제, 대회, 실습의 값 틀 생성, 값 업데이트, 삭제를 진행함.
    class 생성자 호출 시, 과제, 대회, 실습 전체에 대한 Info 생성 및 각 과제, 대회, 실습의 세부 사항 설정을 위한 ContestAnalysis class 호출
'''


class LectureAnalysis(Content):

    def __init__(self):
        Content.__init__(self)
        self.contAnalysis = dict()
        for ctype in ContestType.cTypeList:
            self.contAnalysis[ctype] = ContestAnalysis(self)

    '''
        현재 파라미터로 입력된 문제의 위치(실습, 과제, 대회) 확인 후 해당 문제 ContestAnalysis에서 문제 업데이트 수행
        * contest.lecture_contest_type = contest.model 참조
         
        @param problem : 실습, 과제, 대회 problem
    '''
    def migrateProblem(self, problem):
        contest = problem.contest
        ctype = self.typeSelector(contest.lecture_contest_type)
        self.contAnalysis[ctype].migrateProblem(problem)

        # self.contests[cid].addProblem(problem)
        #
        # if problem.visible is True:
        #     self.totalscore += problem.total_score
        #     self.numofProblems += 1

    '''
        현재 파라미터로 입력된 문제의 위치(실습, 과제, 대회) 확인 후 해당 문제 ContestAnalysis에서 문제 삭제
        * contest.lecture_contest_type = contest.model 참조
         
        @param problem : 실습, 과제, 대회 problem
    '''
    def deleteProblem(self, problem):
        contest = problem.contest
        ctype = self.typeSelector(contest.lecture_contest_type)
        self.contAnalysis[ctype].deleteProblem(problem)

    '''
        현재 파라미터로 입력된 문제의 위치(실습, 과제, 대회) 확인 후 해당 문제 ContestAnalysis에서 Contest 정보 수정
        * contest.lecture_contest_type = contest.model 참조

        @param contest : 실습, 과제, 대회 contest
    '''
    def migrateContest(self, contest):
        ctype = self.typeSelector(contest.lecture_contest_type)
        self.contAnalysis[ctype].migrateContest(contest)

    '''
        현재 파라미터로 입력된 문제의 위치(실습, 과제, 대회) 확인 후 해당 문제 ContestAnalysis에서 Contest 삭제
        * contest.lecture_contest_type = contest.model 참조

        @param contest : 실습, 과제, 대회 contest
    '''
    def deleteContest(self, contest):
        ctype = self.typeSelector(contest.lecture_contest_type)
        self.contAnalysis[ctype].deleteContest(contest)

    '''
        현재 업데이트 정보를 기반으로하여 전체 총괄 정보 업데이트 수행

        @param isMigrate : MigrationList 대상의 값을 업데이트 수행한다.
        @param isAssociate : AssociationClearList 대상의 값을 업데이트 수행한다.
    '''
    def reCalInfo(self, isMigrate, isAssociate):
        self.Info.reCalInfo(self.contAnalysis, isMigrate, isAssociate)

    '''
        DB 값을 통해 조회된 정보가 어떤 타입의 Contest 비교 및 반환 

        @param dbtype : contest.model 에서 조회된 String
    '''
    def typeSelector(self, dbtype):
        if dbtype == ContestType.ASSIGN:
            return ContestType.ASSIGN
        elif dbtype == ContestType.PRACTICE:
            return ContestType.PRACTICE
        elif dbtype == ContestType.CONTEST:
            return ContestType.CONTEST
        else:
            return None

    '''
        특정 문제에서 Submit 을 수행했을 경우 해당 problem의 값을 업데이트 하기위해 사용함.

        @param submission : Submit 수행 후 반환되는 값 (ACCEPTED, PARTIALLY_ACCEPTED)
    '''
    def associateSubmission(self, submission):
        contest = submission.contest
        if contest is not None:
            ctype = self.typeSelector(contest.lecture_contest_type)
            if ctype is not None:
                self.contAnalysis[ctype].associateSubmission(submission)

    '''
        선택된 Lecture's 값을 초기화 진행

        @param X
    '''
    def cleanDataForScorebard(self):
        self.Info.cleanForScoreboard()
        for ca in self.contAnalysis.values():
            ca.cleanDataForScorebard()


class lecDispatcher(LectureAnalysis):
    def __init__(self):
        LectureAnalysis.__init__(self)
        self.id = 0
    '''
        Lecture 정보를 dict 타입으로 변환 및 반환을 진행 
    '''
    def toDict(self):
        ldict = dict()  # Lecture dict
        ldict[LectureDictionaryKeys.INFO] = self.Info.data

        CASdict = dict() # ContestAnalysis dict
        for ckey in self.contAnalysis.keys():
            CA = self.contAnalysis[ckey]
            contsdict = dict() # Contests dict
            for contkey in CA.contests.keys():
                cont = CA.contests[contkey]
                probsdict = dict() # problems dict
                for pkey in cont.problems.keys():
                    probdict = dict()
                    probs = cont.problems[pkey]
                    probdict[LectureDictionaryKeys.INFO] = probs.Info.data
                    probsdict[pkey] = probdict

                contdict = dict()   # specific contest dict
                contdict[LectureDictionaryKeys.CONTEST_TITLE] = cont.title
                contdict[LectureDictionaryKeys.INFO] = cont.Info.data
                contdict[LectureDictionaryKeys.CONTEST_TYPE] = cont.contestType
                contdict[LectureDictionaryKeys.CONTEST_SOLVE_CNT] = cont.solveCount
                contdict[LectureDictionaryKeys.CONTEST_IS_SUBMIT] = cont.isSubmitted
                contdict[LectureDictionaryKeys.PROBLEMS] = probsdict
                contsdict[contkey] = contdict

            CAdict = dict() # specific ContestAnalysis dict
            CAdict[LectureDictionaryKeys.INFO] = CA.Info.data
            CAdict[LectureDictionaryKeys.CONTESTS] = contsdict
            CASdict[ckey] = CAdict

        ldict[LectureDictionaryKeys.CONTESTANALYSIS] = CASdict

        return ldict

    '''
        입력받은 dict type의 값을 업데이트 수행 method 
        
        @param dicdata : Lecture dict
    '''
    def fromDict(self, dicdata):
        if dicdata is None or len(dicdata) == 0:
            return

        self.Info.data = dicdata[LectureDictionaryKeys.INFO]

        for contA in dicdata[LectureDictionaryKeys.CONTESTANALYSIS].keys():
            dicContA = dicdata[LectureDictionaryKeys.CONTESTANALYSIS][contA]
            inContA = self.contAnalysis[contA]
            inContA.Info.data = dicContA[LectureDictionaryKeys.INFO]
            inContA.migrateDictionary(dicContA)


'''
    ContestAnalysis Class : 과제, 대회, 실습의 Contest의 Problem의 목록, 관리를 담당함.
    class 생성자 호출 시, 각 Contest는 사용자에게 기본으로 Visible 상태를 유지하며, LectureAnalysis의 value 기준으로 동작한다.
    @param resLecture : 현재 선택된 Lecture class
'''


class ContestAnalysis(Content):
    resLecture = None

    def __init__(self, resLecture):
        Content.__init__(self)
        self.Info.data[DataType.ISVISIBLE] = True
        self.contests = dict()
        self.resLecture = resLecture

    '''
        현재 파라미터로 입력된 문제의 위치(실습, 과제, 대회) 확인 후 해당 문제 ContestAnalysis에서 문제 업데이트 수행
        cid = Contest cid
        @param problem : 실습, 과제, 대회 problem
    '''
    def migrateProblem(self, problem):
        contest = problem.contest
        cid = contest.id
        resCont = None
        if cid not in self.contests:
            resCont = self.addContest(ResContest(contA=self, contest=contest), cid)
            # print("Add Contest :",resCont.id,resCont.title)
        else:
            resCont = self.contests[cid]

        resCont.migrateproblem(problem)

    '''
        현재 파라미터로 입력된 문제의 위치(실습, 과제, 대회) 확인 후 해당 문제 ContestAnalysis에서 문제 삭제
        cid = Contest cid
        @param problem : 실습, 과제, 대회 problem
    '''
    def deleteProblem(self, problem):
        contest = problem.contest
        cid = contest.id
        resCont = None
        if cid in self.contests:
            resCont = self.contests[cid]
            resCont.deleteProblem(problem)

    '''
        선택된 Contest id에 해당하는 정보 선택 및 수정 요청

        @param contest : 실습, 과제, 대회 contest
    '''
    def migrateContest(self, contest):
        cid = contest.id
        if cid in self.contests:
            self.contests[cid].migrateContest(contest)
        else:
            for move_cont in ContestType.cTypeList:
                if cid in self.resLecture.contAnalysis[move_cont].contests:
                    self.moveContest(contest, move_cont)
                    self.contests[cid].migrateContest(contest)
                    break

    def moveContest(self, contest, target):
        cid = contest.id
        resCont = self.resLecture.contAnalysis[target].contests[cid]
        resCont.contestType = contest.lecture_contest_type
        self.contests[cid] = resCont
        self.resLecture.contAnalysis[target].contests.pop(cid)
        self.reCalInfo(True, True)

    '''
        선택된 Contest id에 해당하는 정보 선택 및 삭제 (Contest List에서 해당 cid값을 가진 value pop)

        @param contest : 실습, 과제, 대회 contest
    '''
    def deleteContest(self, contest):
        cid = contest.id
        if cid in self.contests:
            self.contests.pop(cid)
            self.reCalInfo(True, True)

    '''
        선택된 Contest List에 새로운 Contest 추가 시 사용되는 method
        Contest List cid 추가 후 세부 정보 추가를 위해 contest list class migrate 요청
        
        @param dicData : 추가 할 Problem dict type 정보
    '''
    def migrateDictionary(self, dicData):
        for contestkey in dicData['contests'].keys():
            contDict = dicData['contests'][contestkey]
            #print(contDict)
            cdict = {'id': contestkey,
                     'title': contDict[LectureDictionaryKeys.CONTEST_TITLE],
                     'type': contDict[LectureDictionaryKeys.CONTEST_TYPE],
                     'scnt': contDict[LectureDictionaryKeys.CONTEST_SOLVE_CNT],
                     'issubmit': contDict[LectureDictionaryKeys.CONTEST_IS_SUBMIT],
                     'Info': contDict['Info']}
            resCont = self.addContest(ResContest(contA=self, contDict=cdict), int(contestkey))
            resCont.migrateDictionary(contDict)

    '''
        현재 업데이트 정보를 기반으로하여 전체 Contest info, 총괄 into 정보 업데이트 수행

        @param isMigrate : MigrationList 대상의 값을 업데이트 수행한다.
        @param isAssociate : AssociationClearList 대상의 값을 업데이트 수행한다.
    '''
    def reCalInfo(self, isMigrate, isAssociate):
        self.Info.reCalInfo(self.contests, isMigrate, isAssociate)
        self.resLecture.reCalInfo(isMigrate, isAssociate)

    '''
        선택된 Contest List에 새로운 Contest 추가 시 사용되는 method

        @param resCont : 추가되는 contest의 정보
        @param cid : 새롭게 할당되는 contest의 id
    '''
    def addContest(self, resCont, cid):
        self.contests[cid] = resCont
        return resCont

    '''
        특정 문제에서 Submit 을 수행했을 경우 해당 problem의 값을 업데이트 하기위해 사용함.

        @param submission : Submit 수행 후 반환되는 값 (ACCEPTED, PARTIALLY_ACCEPTED)
    '''
    def associateSubmission(self, submission):
        cid = submission.contest.id
        try:
            selectedContest = self.contests[cid]
        except KeyError:
            selectedContest = self.contests[str(cid)]
        except Exception as e:
            print('Exception ', e)

        if selectedContest is not None:
            selectedContest.associateSubmission(submission)

    '''
        선택된 Contest's 값을 초기화 진행

        @param X
    '''
    def cleanDataForScorebard(self):
        self.Info.cleanForScoreboard()
        for co in self.contests.values():
            co.cleanDataForScorebard()

    def typeSelector(self, dbtype):
        if dbtype == ContestType.ASSIGN:
            return ContestType.ASSIGN
        elif dbtype == ContestType.PRACTICE:
            return ContestType.PRACTICE
        elif dbtype == ContestType.CONTEST:
            return ContestType.CONTEST
        else:
            return None

'''
    ContestAnalysis Class : 과제, 대회, 실습의  Contest cid 기준 선택된 contest 또는 problem을 기준으로 동작
    contest가 새롭게 생성시 contDict값 기준으로 동작
    
    @param contA : 과제, 대회, 실습
    @param contest : 과제, 대회, 실습의 contest
    @param contDict : 새로 생성할 contest의 정보(dict type)
'''


class ResContest(Content):
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

    '''
        선택된 Problem id의 유무 확인 후 없다만 생성, 있다면 정보 수정 을 진행
        * solveCount = numOfTotalProblems을 의미

        @param problem : 실습, 과제, 대회 problem
    '''
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

    '''
        선택된 Problem id에 해당하는 정보 선택 및 삭제 (Problem List에서 해당 pid값을 가진 value pop)

        @param problem : 실습, 과제, 대회 problem
    '''
    def deleteProblem(self, problem):
        pid = problem.id
        if pid in self.problems:
            self.problems.pop(pid)
            self.reCalInfo(isMigrate=True, isAssociate=True)

    '''
        생성된 Contest의 정보를 수정할 경우 해당 method 호출
        
         @param contest : 실습, 과제, 대회 contest
    '''
    def migrateContest(self, contest):
        self.title = contest.title
        self.contestType = self.typeSelector(contest.lecture_contest_type)
        self.Info.data[DataType.ISVISIBLE] = contest.visible
        self.reCalInfo(isMigrate=True, isAssociate=False)

    '''
        선택된 Problem List에 새로운 Contest 추가 시 사용되는 method
        Problem List cid 추가 후 세부 정보 추가를 위해 Problem list class migrate 요청

        @param dicData : 추가 할 Problem dict type 정보
    '''
    def migrateDictionary(self, dicData):
        for probkey in dicData[LectureDictionaryKeys.PROBLEMS].keys():
            problem = dicData[LectureDictionaryKeys.PROBLEMS][probkey]
            probDict = {'id': probkey, 'Info': problem[LectureDictionaryKeys.INFO]}
            self.problems[int(probkey)] = RefProblem(cont=self, probDict=probDict)

    '''
         현재 업데이트 정보를 기반으로하여 전체 Contest info, 총괄 into 정보 업데이트 수행

         @param isMigrate : MigrationList 대상의 값을 업데이트 수행한다.
         @param isAssociate : AssociationClearList 대상의 값을 업데이트 수행한다.
     '''
    def reCalInfo(self, isMigrate, isAssociate):
        if self.Info.data[DataType.ISVISIBLE] is True:
            self.Info.reCalInfo(self.problems, isMigrate, isAssociate)

            # self.checkContestStatus()
            self.contAnalysis.reCalInfo(isMigrate, isAssociate)

            # if all problems of contest have been solved, please count solved contest as below
            # self.checkContestStatus(pinfo)
            #
            #
            # self.contAnalysis.reCalInfo(pinfo)

    '''
        DB 값을 통해 조회된 정보가 어떤 타입의 Contest 비교 및 반환 

        @param dbtype : contest.model 에서 조회된 String
    '''
    def typeSelector(self, dbtype):
        if dbtype == ContestType.ASSIGN:
            return ContestType.ASSIGN
        elif dbtype == ContestType.PRACTICE:
            return ContestType.PRACTICE
        elif dbtype == ContestType.CONTEST:
            return ContestType.CONTEST

    '''
         특정 문제에서 Submit 을 수행했을 경우 해당 problem의 값을 업데이트 하기위해 사용함.

         @param submission : Submit 수행 후 반환되는 값 (ACCEPTED, PARTIALLY_ACCEPTED)
     '''
    def associateSubmission(self, submission):
        pid = submission.problem.id
        try:
            subprob = self.problems[pid]
        except KeyError:
            subprob = self.problems[str(pid)]
        except Exception as e:
            print("Exception ", e)
        if subprob is not None:
            subprob.associateSubmission(submission)

    '''
        선택된 Submitted, 문제 푼 개수 등 Contest-problem 값을 초기화 진행

        @param X
    '''
    def cleanDataForScorebard(self):
        self.isSubmitted = False
        self.solveCount = len(self.problems)
        self.Info.cleanForScoreboard()
        for po in self.problems.values():
            po.cleanDataForScorebard()


'''
    ContestAnalysis Class : 과제, 대회, 실습의  Contest cid 기준 선택된 contest 또는 problem을 기준으로 동작
    contest가 새롭게 생성시 contDict값 기준으로 동작

    @param cont : 과제, 대회, 실습의 contest
    @param problem : contest에서 선택된 problem
    @param contDict : 새로 생성할 problem의 정보(dict type)
'''


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

    '''
        문제의 값 변경, 생성시 사용되는 method
        
        @param problem : problem의 정보, 새로 생성할 problem의 정보(dict type)
    '''
    def migrateProblem(self, problem):
        self.title = problem.title
        self.Info.data[DataType.POINT] = problem.total_score
        self.Info.data[DataType.ISVISIBLE] = problem.visible
        self.Info.data[DataType.NUMOFCONTENTS] = 1
        self.Info.data[DataType.NUMOFTOTALPROBLEMS] = 1

        self.pcontest.reCalInfo(isMigrate=True, isAssociate=False)

    '''
         특정 문제에서 Submit 을 수행했을 경우 해당 problem의 값을 업데이트 하기위해 사용함.

         @param submission : Submit 수행 후 반환되는 값 (ACCEPTED, PARTIALLY_ACCEPTED)
     '''
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
        # passed -> fail
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

    '''
        선택된 problem 값을 초기화 진행

        @param X
    '''
    def cleanDataForScorebard(self):
        self.Info.cleanForScoreboard()
