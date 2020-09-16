import os
import sys
import json
import django

from utils.shortcuts import rand_str

sys.path.append("../../")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oj.settings")
django.setup()
from problem.models import Problem


def copy_dataset_create(problems):
    # copy dataset create
    for _prob in problems:
        test_case_id = rand_str()  # create new id
        from django.conf import settings
        test_case_dir = os.path.join(settings.TEST_CASE_DIR, test_case_id)
        origin_test_case_dir = os.path.join(settings.TEST_CASE_DIR, _prob.test_case_id)
        if not os.path.isdir(test_case_dir):
            # os.mkdir(test_case_dir)
            import shutil
            shutil.copytree(origin_test_case_dir, test_case_dir)  # copy_dataset
        print(": change testCase id")

        _prob.test_case_id = test_case_id
        _prob.save()

        os.chmod(test_case_dir, 0o710)


def main():
    try:
        print("Try")
        Problems = Problem.objects.all()
    except:
        print("exception")

    changed_id_list = []
    cnt = 0
    for prob in Problems:
        cnt += 1
        if prob.contest:
            if prob.contest.lecture:
                print("(",prob.contest.lecture.id,")",prob.contest.lecture.title,": ", prob.contest.title,": ",prob.title)
            else:
                print(prob.contest.title, prob.title)
        else:
            print(prob.title)
        if prob.id in changed_id_list:
            print(": Already change this id")
            pass
        else:
            changed_id_list.append(prob.id)

        same_testCase_prob = Problem.objects.filter(test_case_id=prob.test_case_id)

        if same_testCase_prob.count() > 1:
            copy_dataset_create(same_testCase_prob)
        else:
            print(": Do not need change this id")


main()