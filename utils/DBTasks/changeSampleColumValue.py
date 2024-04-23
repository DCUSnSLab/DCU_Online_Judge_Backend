import os
import sys
import django
from django.conf import settings
sys.path.append("../../")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oj.settings")
django.setup()
from problem.models import Problem
def changeValue():
    try:
        print("try get data")
        Problems = Problem.objects.all()
        print("probles Get")
        for problem in Problems:
            test_case_dir = os.path.join(settings.TEST_CASE_DIR, problem.test_case_id)
            newSampleData = []
            sampleLen = len(problem.samples)
            for i in range(sampleLen):
                testCaseData = {}
                with open(test_case_dir + '/' + str(i+1) + '.in', "r") as f:
                    testCaseData['input'] = ''.join(f.readlines()).strip()
                with open(test_case_dir + '/' + str(i+1) + '.out', "r") as f:
                    testCaseData['output'] = ''.join(f.readlines()).strip()
                newSampleData.append(testCaseData)
            problem.samples = newSampleData
            problem.save()
            print("problem.id: ", problem.id , "success save")
    except:
        print("except")
changeValue()
