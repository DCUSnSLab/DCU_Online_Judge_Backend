import errno
import shutil
import sys
import os
import numpy as np
import pandas as pd
from subprocess import Popen, PIPE
#from sqlmanager import SQLManager
from submission.models import Submission
from django.db.models import Max
import json

class PlagChecker:
    data = None

    def __init__(self, _lid=-1, _cid=-1, _pid=-1, _multi=False):
        self.CheckRoomPath = './data/copykiller/checkroom'
        self.ResultRoomPath = './data/copykiller/resultroom'
        self.multi = _multi
        self.lid = _lid
        self.cid = _cid
        self.pid = _pid

        self.subDirName = ""
        self.chkRoom_SubDirPath = ""
        self.ResRoom_SubDirPath = ""

        self.selectedLang = ""
        self.DataRowCnt = 0
        self.DataExist = False

        #subdatas = {userID : submission ID}
        self.matchlist = dict()

    def runChecker(self):
        data = self.loadSubmissionData()
        print(data)
        self.makeSourceFiles(data)
        self.doChecker()

        return self.ResRoom_SubDirPath

    def runMultiChecker(self):
        data = self.loadSubmissionDatas()
        print(data)
        self.makeMultiLectureSourceFiles(data)
        self.doChecker()

        return self.ResRoom_SubDirPath

    def loadSubmissionData(self):
        data = Submission.objects.filter(lecture=self.lid, contest=self.cid, problem=self.pid)

        self.DataRowCnt = data.count()

        if self.DataRowCnt != 0:
            self.DataExist = True
            #Check Language
            self.selectedLang = self.LanguageInterface(data[0].language)

        return data

    def loadSubmissionDatas(self):
        data = list()

        for lec, cont, prob in zip(self.lid, self.cid, self.pid):
            sub = Submission.objects.filter(lecture=lec, contest=cont, problem=prob)

            self.DataRowCnt = sub.count()

            if self.DataRowCnt != 0:
                self.DataExist = True
                # Check Language
                self.selectedLang = self.LanguageInterface(sub[0].language)

                data.append(sub)

        return data

    def testset(self, d):
        return d[d['create_time'] == d['create_time'].max()]

    def DataSelector(self, data):
        #data = data.groupby('user_id').apply(self.testset)
        data = data.values('user', 'contest', 'problem').annotate(latest_created_at=Max('create_time'))
        return data

    def makeMultiLectureSourceFiles(self, data):
        filechecker = True
        #make base directory
        if self.checkDirectory(self.CheckRoomPath):
            #make submission dir
            print('make sub directory')
            if self.lid == -1:
                lidname = 'x'
            else:
                lidname = str(self.lid[0])

            self.subDirName = '/sub_' + lidname + '_' + str(self.cid[0]) + '_' + str(self.pid[0])
            self.chkRoom_SubDirPath = self.CheckRoomPath + self.subDirName
            self.ResRoom_SubDirPath = self.ResultRoomPath + self.subDirName

            #Make Submission Dir
            if self.checkDirectory(self.chkRoom_SubDirPath, True):
                print('make files..')
                rcnt = 0
                for lec in data:
                    for rdata in lec:
                        uid = str(rdata.user.schoolssn)
                        if rcnt == 0:
                            siddir = self.chkRoom_SubDirPath + '/target_sid_' + str(self.lid[rcnt]) + "_" + str(uid)
                        else:
                            siddir = self.chkRoom_SubDirPath + '/sid_' + str(self.lid[rcnt]) + "_" + str(uid)
                        if self.checkDirectory(siddir) is True:
                            filename = siddir + '/code_' + str(self.lid[rcnt]) + "_" + uid + self.languageChecker(rdata.language)
                            self.makeText(filename, rdata.code)
                        else:
                            filechecker = False
                    rcnt += 1
            else:
                filechecker = True
        else:
            filechecker = True

        return filechecker

    def makeSourceFiles(self, data):
        filechecker = True
        #make base directory
        if self.checkDirectory(self.CheckRoomPath):
            #make submission dir
            print('make sub directory')
            if self.lid == -1:
                lidname = 'x'
            else:
                lidname = str(self.lid)

            self.subDirName = '/sub_' + lidname + '_' + str(self.cid) + '_' + str(self.pid)
            self.chkRoom_SubDirPath = self.CheckRoomPath + self.subDirName
            self.ResRoom_SubDirPath = self.ResultRoomPath + self.subDirName

            #Make Submission Dir
            if self.checkDirectory(self.chkRoom_SubDirPath, True):
                print('make files..')
                rcnt = 1
                for rdata in data:
                    uid = str(rdata.user.schoolssn)
                    siddir = self.chkRoom_SubDirPath + '/sid_' + str(self.lid) + "_" + str(uid)
                    if self.checkDirectory(siddir) is True:

                        filename = siddir + '/code_' + str(self.lid) + "_" + uid + self.languageChecker(rdata.language)
                        self.makeText(filename, rdata.code)
                        rcnt += 1
                    else:
                        filechecker = False
            else:
                filechecker = True
        else:
            filechecker = True

        return filechecker

    def checkDirectory(self, name, delExist = False):
        try:
            if os.path.isdir(name) and delExist:
                shutil.rmtree(os.path.join(name))

            if not os.path.isdir(name):
                os.makedirs(os.path.join(name))
            return True
        except OSError as e:
            if e.errno != errno.EEXIST:
                print("Failed to create directory")
            return False

    def makeText(self, fullpath, data):
        text = open(fullpath, 'w')
        text.write(data)
        text.close()

    def languageChecker(self, data):
        ret = "."
        if data == 'C':
            ret += 'c'
        elif data == 'C++':
            ret += 'cpp'
        elif data == 'Python3' or data == 'Python2':
            ret += 'py'
        elif data == 'Java':
            ret += 'java'
        else:
            ret += 'no'
        return ret

    def LanguageInterface(self, lang):
        ret = ""
        if lang == 'C':
            ret += 'c/c++'
        elif lang == 'C++':
            ret += 'c/c++'
        elif lang == 'Python3' or lang == 'Python2':
            ret += 'python3'
        elif lang == 'Java':
            ret += 'java11'
        else:
            ret += 'no'
        return ret

    def doChecker(self):
        import os
        p = Popen(['java', '-jar', os.getcwd()+'/utils/PlagiarismChecker/Plag/jplag/jplag-2.12.1-SNAPSHOT-jar-with-dependencies.jar', '-l', self.selectedLang, '-s', self.chkRoom_SubDirPath, '-r', self.ResRoom_SubDirPath], stdin=PIPE, stdout=PIPE)
        stdout = p.communicate()[0]
        print('STDOUT:{}'.format(stdout))
        #self.matchClassifier(stdout)
        #cmd = 'java -jar ./jplag/jplag-2.12.1-SNAPSHOT-jar-with-dependencies.jar -l c/c++ -s ../checkroom/'
        #os.system(cmd)

    def matchClassifier(self, data):
        class_text = 'Comparing '
        tlist = str(data).split("\\n")

        print("enter text")
        for tdata in tlist:
            if class_text in tdata:
                uid1 = int(tdata.split("sid_")[1].split("-")[0])
                uid2 = int(tdata.split("sid_")[2].split(":")[0])
                score = float(tdata.split("sid_")[2].split(": ")[1].replace("\\r",""))

                if not self.matchlist.get(uid1):
                    self.matchlist[uid1] = dict()
                self.matchlist[uid1][uid2] = score

                if not self.matchlist.get(uid2):
                    self.matchlist[uid2] = dict()
                self.matchlist[uid2][uid1] = score

                #print(uid1, uid2, score)

        #print(self.matchlist)

    def DISTtoJSON(self, ddata):
        #convert to json
        app_json = json.dumps(ddata)
        return app_json

def singleLecture(lec, cont, prob):
    PC = PlagChecker(_lid=lec, _cid=cont, _pid=prob)
    return PC.runChecker()

def multiLecture(lecList, contList, probList):
    PC = PlagChecker(_lid=lecList, _cid=contList, _pid=probList, _multi=True)
    return PC.runMultiChecker()