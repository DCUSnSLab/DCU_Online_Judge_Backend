from utils.api import UsernameSerializer, serializers

from .models import Lecture, signup_class, ta_admin_class


class CreateLectureSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=128)
    description = serializers.CharField()
    status = serializers.BooleanField()
    password = serializers.CharField(allow_blank=True, max_length=32)
    year = serializers.IntegerField()
    semester = serializers.IntegerField()
    created_by_id = serializers.IntegerField()

class EditTAuserSerializer(serializers.Serializer):
    permit = serializers.ListField(child=serializers.CharField(max_length=128))
    ssn = serializers.IntegerField()

class EditLectureSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField(max_length=128)
    description = serializers.CharField()
    status = serializers.BooleanField()
    password = serializers.CharField(allow_blank=True, max_length=32)
    year = serializers.IntegerField()
    semester = serializers.IntegerField()
    created_by_id = serializers.IntegerField()

class LectureAdminSerializer(serializers.ModelSerializer):
    created_by = UsernameSerializer()

    class Meta:
        model = Lecture
        fields = "__all__"

class TAAdminSerializer(serializers.ModelSerializer):
    checklist = serializers.ListField(child=serializers.CharField(max_length=128))
    class Meta:
        model = ta_admin_class
        fields = "__all__"

class LectureSerializer(LectureAdminSerializer):
    class Meta:
        model = Lecture
        fields = "__all__"

class SimpleLectureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lecture
        fields = "__all__"

class SignupClassSerializer(serializers.ModelSerializer):
    lecture = LectureSerializer()
    class Meta:
        model = signup_class
        fields = "__all__"

class PermitTA(object):
    PROBLEM = "문제 수정"
    CODE = "답안 확인"
    SCORE = "점수 확인"