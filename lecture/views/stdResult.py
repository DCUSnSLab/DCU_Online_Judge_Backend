from problem.models import Problem
from contest.models import Contest
from submission.models import Submission, JudgeStatus
from lecture.models import Lecture, signup_class

class ContestType(object):
    PRACTICE = "실습"
    ASSIGN = "과제"

class ContestClassifier:
    numofContest = 0

    def __init__(self):
        self.contestIndex = list()

    def addIndexer(self, RContest):
        self.numofContest += 1
        self.contestIndex.append(RContest.id)

class RefLecture:

    totalscore = 0
    numofProblems = 0
    numofContests = 0

    def __init__(self):
        self.contests = dict()
        self.contClass = dict()

        self.contClass[ContestType.PRACTICE] = ContestClassifier()
        self.contClass[ContestType.ASSIGN] = ContestClassifier()

    def addProblem(self, problem):
        cid = problem.contest_id

        if cid not in self.contests:
            self.addContest(RefContest(problem.contest), cid)

        self.contests[cid].addProblem(problem)

        if problem.visible is True:
            self.totalscore += problem.total_score
            self.numofProblems += 1

    def addContest(self, rcontest, cid):
        self.contests[cid] = rcontest
        self.numofContests += 1

    def getContestInfo(self, cid):
        return self.contests[cid]

    def getProblemInfo(self, cid, pid):
        return self.contests[cid].problems[pid]

class RefContest:
    title = ""
    id = -1

    totalScore = 0
    numofProblems = 0

    def __init__(self, contest):
        self.problems = dict()
        self.myContest = None
        self.id = contest.id
        self.title = contest.title
        self.cate = self.typeSelector(contest.lecture_contest_type)
        self.myContest = contest

    def typeSelector(self, dbtype):
        if dbtype == "과제":
            return ContestType.ASSIGN
        else:
            return ContestType.PRACTICE

    def addProblem(self, prob):
        inprob = RefProblem(prob)
        if prob.visible is True:
            self.totalScore += inprob.score
            self.numofProblems += 1

        self.problems[prob.id] = inprob


class RefProblem:
    score = 0
    isvisible = False

    def __init__(self, problem):
        self.myproblem = None
        self.migrateProblem(problem)

    def migrateProblem(self, problem):
        self.myproblem = problem
        self.score = problem.total_score
        self.isvisible = problem.visible

    def getProblemID(self):
        return self.myproblem.id

    def getProblemTitle(self):
        return self.myproblem.title



class SubmitLecture:
    student_id = -1
    totalscore = 0
    problemAverage = 0
    contestAverage = 0
    totalContestScore = 0
    totalProblems = 0
    submittedProblems = 0
    passedProblems = 0
    progress = 0;

    LectureInfo = None

    def __init__(self, signup_info, lecinfo):
        self.studentInfo = signup_info
        self.student_id = signup_info.user_id
        self.LectureInfo = lecinfo
        self.totalProblems = lecinfo.numofProblems
        self.contests = dict()


    def addSubmission(self, submission):
        proinfo = self.LectureInfo.getProblemInfo(cid=submission.contest_id, pid=submission.problem_id)
        if proinfo.isvisible is True:
            cid = submission.contest_id
            sid = submission.problem_id

            if cid not in self.contests:
                self.contests[cid] = SubmitContest(submission, self.LectureInfo.contests[cid])

            self.passedProblems -= self.contests[cid].passedProblems

            self.contests[cid].addProblem(submission)

            self.submittedProblems += 1
            self.totalscore += self.contests[cid].problems[sid].myscore
            self.passedProblems += self.contests[cid].passedProblems


            if self.totalProblems != 0:
                self.totalContestScore = 0

                for con in self.contests.values():
                    self.totalContestScore += con.percentage

                self.problemAverage = round(self.totalscore * 100 / self.LectureInfo.totalscore, 2)
                self.contestAverage = round(self.totalContestScore / self.LectureInfo.numofContests, 2)
                self.progress = self.submittedProblems / self.totalProblems * 100

class SubmitContest:
    id = -1

    totalScore = 0
    percentage = 0
    numofProblems = 0
    passedProblems = 0
    ContestInfo = None

    def __init__(self, submission, rcon):
        self.ContestInfo = rcon
        self.problems = dict()
        self.id = submission.contest_id

    def addProblem(self, submission):
        inprob = SubmitProblem(submission, self.ContestInfo.problems[submission.problem_id])
        self.totalScore += inprob.myscore
        self.numofProblems += 1

        if inprob.ispassed is True:
            self.passedProblems += 1

        self.problems[inprob.id] = inprob

        self.percentage = self.totalScore * 100 / self.ContestInfo.totalScore


class SubmitProblem:
    id = -1
    myscore = 0
    ispassed = False
    ProblemInfo = None

    def __init__(self, submission, pinfo):
        self.ProblemInfo = pinfo
        self.mysubmission = None
        self.migrateProblem(submission)

    def migrateProblem(self, submission):
        self.mysubmission = submission
        self.id = submission.problem_id
        Json = submission.info

        if Json:  # 해당 사용자의 submit 이력이 있는 경우 (Submission에 사용자의 id값이 포함된 값이 있는 경우)
            for jsondata in Json['data']:
                self.myscore += jsondata['score']

        if submission.result == JudgeStatus.ACCEPTED:
            self.ispassed = True

    def getProblemID(self):
        return self.mysubmission.problem_id

    def getProblemTitle(self):
        return self.myproblem.problem.title

