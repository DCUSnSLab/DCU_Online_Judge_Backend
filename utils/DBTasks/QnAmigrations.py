import os
import sys
import json
import django

sys.path.append("../../")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oj.settings")
django.setup()

from qna.models import Post, Comment
from account.models import User

try:
    print("Try")
    post = Post.objects.all()
    comment = Comment.objects.all()
except:
    print("exception")
#User.is_admin_role()
for qna in post:
    post_comment = comment.filter(post=qna).order_by('-date_posted')
    print(qna.title)
    if post_comment.exists():
        post_comment = post_comment[0]
        if post_comment.author.is_admin() or post_comment.author.is_semi_admin() or post_comment.author.is_super_admin() :
            qna.proceeding = False
        else:
            qna.proceeding = True
        qna.save()
    else:
        qna.proceeding = True
        qna.save()
        pass