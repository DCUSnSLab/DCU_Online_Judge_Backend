from problem.models import Problem
from contest.models import Contest
from submission.models import Submission, JudgeStatus
from lecture.models import Lecture, signup_class

class GroupType(object):
    LECTURE = 'gt_lecture'
    CONTEST = 'gt_contest'
    PROBLEM = 'gt_problem'
    gtypeList = [LECTURE, CONTEST, PROBLEM]

class ContestType(object):
    PRACTICE = "실습"
    ASSIGN = "과제"
    cTypeList = [PRACTICE, ASSIGN]

class Score:
    totalscore = 0
    numofContents = 0
    average = 0

class LectureAnalysis:
    def __init__(self):
        self.RefScore = dict()
        self.contests = dict()
        self.initResScore()

    def initResScore(self):
        self.RefScore[GroupType.CONTEST] = Score()
        self.RefScore[GroupType.PROBLEM] = Score()

    def addProblem(self, problem):
        cid = problem.contest_id

        # if cid not in self.contests:
        #     self.addContest(RefContest(problem.contest), cid)

        self.contests[cid].addProblem(problem)

        if problem.visible is True:
            self.totalscore += problem.total_score
            self.numofProblems += 1

    def addContest(self, rcontest, cid):
        self.contests[cid] = rcontest
        self.numofContests += 1

class ContestAnalysis:
    def __init__(self):
        self.RefScore = dict()
        self.contests = dict()