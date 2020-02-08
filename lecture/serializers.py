from utils.api import UsernameSerializer, serializers

from .models import Lecture


class CreateLectureSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=128)
    description = serializers.CharField()
    status = serializers.BooleanField()

class EditLectureSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField(max_length=128)
    description = serializers.CharField()
    status = serializers.BooleanField()

class LectureAdminSerializer(serializers.ModelSerializer):
    created_by = UsernameSerializer()

    class Meta:
        model = Lecture
        fields = "__all__"


class LectureSerializer(LectureAdminSerializer):
    class Meta:
        model = Lecture
        fields = "__all__"

