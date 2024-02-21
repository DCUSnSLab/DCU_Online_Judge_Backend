import os
from datetime import timedelta
from importlib import import_module

import qrcode
from django.conf import settings
from django.contrib import auth
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from otpauth import OtpAuth

from lecture.views.LectureBuilder import UserBuilder
from problem.models import Problem
from contest.models import Contest, ContestUser
from utils.shortcuts import send_email
from utils.constants import ContestRuleType
from options.options import SysOptions
from utils.api import APIView, validate_serializer, CSRFExemptAPIView
from utils.captcha import Captcha
from utils.shortcuts import rand_str, img2base64, datetime2str
from ..decorators import login_required
from ..models import User, UserProfile, AdminType
from ..serializers import (ApplyResetPasswordSerializer, ResetPasswordSerializer,
                           UserChangePasswordSerializer, UserLoginSerializer,
                           UserRegisterSerializer, UsernameOrEmailCheckSerializer,
                           RankInfoSerializer, UserChangeEmailSerializer, SSOSerializer, SignupSerializer, MainSignupSerializer)
from ..serializers import (TwoFactorAuthCodeSerializer, UserProfileSerializer,
                           EditUserProfileSerializer, ImageUploadForm)
from ..tasks import send_email_async

from lecture.models import signup_class, Lecture
from contest.models import Contest, ContestUser  # working by soojung
from django.db.models import Max
from lecture.views.LectureAnalysis import LectureAnalysis, DataType, ContestType, lecDispatcher


class UserProfileAPI(APIView):
    @method_decorator(ensure_csrf_cookie)
    def get(self, request, **kwargs):
        """
        判断是否登录， 若登录返回用户信息
        """
        user = request.user
        if not user.is_authenticated:
            return self.success()
        show_real_name = False
        username = request.GET.get("username")
        try:
            if username:
                user = User.objects.get(username=username, is_disabled=False)
            else:
                user = request.user
                # api返回的是自己的信息，可以返real_name
                show_real_name = True
        except User.DoesNotExist:
            return self.error("User does not exist")
        return self.success(UserProfileSerializer(user.userprofile, show_real_name=show_real_name).data)

    @validate_serializer(EditUserProfileSerializer)
    @login_required
    def put(self, request):
        data = request.data
        user_profile = request.user.userprofile
        user = User.objects.get(id=request.user.id)

        for k, v in data.items():
            setattr(user_profile, k, v)
        if data['realname']:
            user.realname = data['realname']
        #test = User.objects.filter(schoolssn=data['schoolssn']).exclude(schoolssn=user.schoolssn).exists()
        if User.objects.filter(schoolssn=data['schoolssn']).exclude(schoolssn=user.schoolssn).exists():
            return self.error("중복된 학번입니다.")
        user.schoolssn = data['schoolssn']
        user.save()
        user_profile.save()
        return self.success(UserProfileSerializer(user_profile, show_real_name=True).data)

class UserProgress(APIView):
    @login_required
    def get(self, request):
        if not request.user.is_authenticated:
            return self.error("로그인 후 사용 가능합니다.")

        if request.user.is_super_admin(): # 관리자 계정의 개설 과목 출력
            return
        print(request.user)

        from datetime import datetime
        year = datetime.today().year
        semester = (8 > datetime.today().month >= 3) and 1 or (3 > datetime.today().month >= 1) and 3 or 2

        try:
            lectures = signup_class.objects.filter(user_id=request.user, isallow=True, lecture__year=year, lecture__semester=semester).select_related('lecture')
            # ulist = ulist.exclude(user__admin_type__in=[AdminType.ADMIN, AdminType.SUPER_ADMIN])
        except signup_class.DoesNotExist:
            return self.error("수강중인 학생이 없습니다.")

        for lec in lectures:
            #print(lec.lecture.title)
            #collect lecture info
            plist = Problem.objects.filter(contest__lecture=lec.lecture_id).prefetch_related('contest')

            #test
            LectureInfo = lecDispatcher()
            # for p in plist:
            #     # print(p.id,p.title,p.visible)
            #     LectureInfo.migrateProblem(p)
            #
            # LectureInfo.cleanDataForScorebard()
            LectureInfo.fromDict(lec.score)

            #inlit result values
            lec.totalPractice = 0
            lec.subPractice = 0
            lec.solvePractice = 0

            lec.totalAssign = 0
            lec.subAssign = 0
            lec.solveAssign = 0

            lec.tryProblem = 0
            lec.solveProblem = 0
            lec.totalScore = 0
            lec.avgScore = 0
            lec.progress = 0
            lec.totalProblem = 0
            lec.maxScore = 0
            lec.lecDict = dict()

            lec.totalPractice = LectureInfo.contAnalysis[ContestType.PRACTICE].Info.data[DataType.NUMOFCONTENTS]
            lec.subPractice = LectureInfo.contAnalysis[ContestType.PRACTICE].Info.data[DataType.NUMOFSUBCONTENTS]
            lec.solvePractice = LectureInfo.contAnalysis[ContestType.PRACTICE].Info.data[DataType.NUMOFSOLVEDCONTENTS]

            lec.totalAssign = LectureInfo.contAnalysis[ContestType.ASSIGN].Info.data[DataType.NUMOFCONTENTS]
            lec.subAssign = LectureInfo.contAnalysis[ContestType.ASSIGN].Info.data[DataType.NUMOFSUBCONTENTS]
            lec.solveAssign = LectureInfo.contAnalysis[ContestType.ASSIGN].Info.data[DataType.NUMOFSOLVEDCONTENTS]

            lec.tryProblem = LectureInfo.Info.data[DataType.NUMOFTOTALSUBPROBLEMS]
            lec.solveProblem = LectureInfo.Info.data[DataType.NUMOFTOTALSOLVEDPROBLEMS]
            lec.totalScore = LectureInfo.Info.data[DataType.SCORE]
            lec.avgScore = LectureInfo.Info.data[DataType.AVERAGE]
            lec.progress = LectureInfo.Info.data[DataType.PROGRESS]

            lec.totalProblem = LectureInfo.Info.data[DataType.NUMOFTOTALPROBLEMS]
            lec.maxScore = LectureInfo.Info.data[DataType.POINT]

            try:
                contestlist = Contest.objects.filter(lecture=lec.lecture.id, start_time__lte=now(), end_time__gte=now()).order_by('end_time')
            except:
                print("contest no exists")

            lec.contestlist = dict()

            for idx, contest in enumerate(contestlist):
                condict = dict()
                condict['id'] = contest.id
                condict['end_time'] = str(contest.end_time)
                condict['title'] = contest.title
                condict['description'] = contest.description
                total = LectureInfo.contAnalysis[contest.lecture_contest_type].contests[contest.id].Info.data[DataType.NUMOFCONTENTS]
                solved = LectureInfo.contAnalysis[contest.lecture_contest_type].contests[contest.id].Info.data[DataType.NUMOFSOLVEDCONTENTS]
                condict['remainproblem'] = total - solved
                print("테스트 출력",condict['remainproblem'])
                if condict['remainproblem'] != 0:
                    lec.contestlist[idx] = condict

        return self.success(self.paginate_data(request, lectures, MainSignupSerializer))

class AvatarUploadAPI(APIView):
    request_parsers = ()

    @login_required
    def post(self, request):
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            avatar = form.cleaned_data["image"]
        else:
            return self.error("Invalid file content")
        if avatar.size > 2 * 1024 * 1024:
            return self.error("Picture is too large")
        suffix = os.path.splitext(avatar.name)[-1].lower()
        if suffix not in [".gif", ".jpg", ".jpeg", ".bmp", ".png"]:
            return self.error("Unsupported file format")

        name = rand_str(10) + suffix
        with open(os.path.join(settings.AVATAR_UPLOAD_DIR, name), "wb") as img:
            for chunk in avatar:
                img.write(chunk)
        user_profile = request.user.userprofile

        user_profile.avatar = f"{settings.AVATAR_URI_PREFIX}/{name}"
        user_profile.save()
        return self.success("Succeeded")


class TwoFactorAuthAPI(APIView):
    @login_required
    def get(self, request):
        """
        Get QR code
        """
        user = request.user
        if user.two_factor_auth:
            return self.error("2FA is already turned on")
        token = rand_str()
        user.tfa_token = token
        user.save()

        label = f"{SysOptions.website_name_shortcut}:{user.username}"
        image = qrcode.make(OtpAuth(token).to_uri("totp", label, SysOptions.website_name.replace(" ", "")))
        return self.success(img2base64(image))

    @login_required
    @validate_serializer(TwoFactorAuthCodeSerializer)
    def post(self, request):
        """
        Open 2FA
        """
        code = request.data["code"]
        user = request.user
        if OtpAuth(user.tfa_token).valid_totp(code):
            user.two_factor_auth = True
            user.save()
            return self.success("Succeeded")
        else:
            return self.error("Invalid code")

    @login_required
    @validate_serializer(TwoFactorAuthCodeSerializer)
    def put(self, request):
        code = request.data["code"]
        user = request.user
        if not user.two_factor_auth:
            return self.error("2FA is already turned off")
        if OtpAuth(user.tfa_token).valid_totp(code):
            user.two_factor_auth = False
            user.save()
            return self.success("Succeeded")
        else:
            return self.error("Invalid code")


class CheckTFARequiredAPI(APIView):
    @validate_serializer(UsernameOrEmailCheckSerializer)
    def post(self, request):
        """
        Check TFA is required
        """
        data = request.data
        result = False
        if data.get("username"):
            try:
                user = User.objects.get(username=data["username"])
                result = user.two_factor_auth
            except User.DoesNotExist:
                pass
        return self.success({"result": result})


class UserLoginAPI(APIView):
    @method_decorator(csrf_exempt)
    @validate_serializer(UserLoginSerializer)
    def post(self, request):
        """
        User login api
        """
        data = request.data
        user = auth.authenticate(username=data["username"], password=data["password"])
        # None is returned if username or password is wrong
        if user:
            if user.is_disabled:
                return self.error("Your account has been disabled")
            if not user.two_factor_auth:
                auth.login(request, user)
                return self.success("Succeeded")

            # `tfa_code` not in post data
            if user.two_factor_auth and "tfa_code" not in data:
                return self.error("tfa_required")

            if OtpAuth(user.tfa_token).valid_totp(data["tfa_code"]):
                auth.login(request, user)
                return self.success("Succeeded")
            else:
                return self.error("Invalid two factor verification code")
        else:
            return self.error("Invalid username or password")


class UserLogoutAPI(APIView):
    def get(self, request):
        userID = request.user.id
        if request.user.is_student():
            if ContestUser.objects.filter(user_id=userID, end_time__isnull=True).exists(): # working by soojung
                ContestUser.objects.filter(user_id=userID, end_time__isnull=True).update(end_time=now())
            # contestlog_list = []
            # contestlog_list.append(ContestUser.objects.filter(user_id=userID, end_time__isnull=True))
            # print(contestlog_list)
            # auth.logout(request)
        auth.logout(request)
        return self.success()


class UsernameOrEmailCheck(APIView):
    @validate_serializer(UsernameOrEmailCheckSerializer)
    def post(self, request):
        """
        check username or email is duplicate
        """
        data = request.data
        # True means already exist.
        
        print("Test")
        result = {
            "username": False,
            "email": False,
            "schoolssn_valid": False,
            "schoolssn": False
        }
        if data.get("username"):
            result["username"] = User.objects.filter(username=data["username"].lower()).exists()
        if data.get("email"):
            result["email"] = User.objects.filter(email=data["email"].lower()).exists()
        if data.get("schoolssn"):
            result["schoolssn"] = User.objects.filter(schoolssn=data["schoolssn"]).exists()

        return self.success(result)

class SchoolssnCheck(APIView):
    @validate_serializer(UsernameOrEmailCheckSerializer)
    def post(self, request):
        """
        check schoolssn is duplicate
        """
        data = request.data
        # True means already exist.
        result = {
            "schoolssn": False
        }
        if data.get("schoolssn"):
            result["schoolssn"] = User.objects.filter(username=data["username"].lower()).exists()
        return self.success(result)

class UserRegisterAPI(APIView):
    @validate_serializer(UserRegisterSerializer)
    def post(self, request):
        """
        User register api
        """
        if not SysOptions.allow_register:
            return self.error("Register function has been disabled by admin")

        data = request.data
        data["username"] = data["username"].lower()
        data["email"] = data["email"].lower()
        captcha = Captcha(request)
        if not captcha.check(data["captcha"]):
            return self.error("Invalid captcha")
        if User.objects.filter(username=data["username"]).exists():
            return self.error("Username already exists")
        if User.objects.filter(email=data["email"]).exists():
            return self.error("Email already exists")
        if User.objects.filter(schoolssn=data["schoolssn"]).exists():
            return self.error("학번/교직번호가 이미 있습니다.")
        #print(data["realname"])
        user = User.objects.create(username=data["username"], email=data["email"], schoolssn=data["schoolssn"], realname=data["realname"])

        """
        2020-03-14 현재 수강신청 자동화 기능 개선
        lecture_signup_class에서 동일한 학번을 가진 값이 있는지 필터를 통해 구해오고,
        있는 경우, 해당 값들의 isallow를 전부 True로 수정한다.
        """
        print("학번",data["schoolssn"])
        try:
            print("try")
            signup_list = signup_class.objects.filter(schoolssn=data["schoolssn"])
            print(signup_list)
            print(user)
            for signup in signup_list:
                signup.user = user
                signup.isallow = True
                signup.save()

            ub = UserBuilder(None)
            ub.buildLecturebyUser(user)
        except:
            print("no matching singup_class")

        user.set_password(data["password"])
        user.save()
        UserProfile.objects.create(user=user)
        return self.success("Succeeded")


class UserChangeEmailAPI(APIView):
    @validate_serializer(UserChangeEmailSerializer)
    @login_required
    def post(self, request):
        data = request.data
        user = auth.authenticate(username=request.user.username, password=data["password"])
        if user:
            if user.two_factor_auth:
                if "tfa_code" not in data:
                    return self.error("tfa_required")
                if not OtpAuth(user.tfa_token).valid_totp(data["tfa_code"]):
                    return self.error("Invalid two factor verification code")
            data["new_email"] = data["new_email"].lower()
            if User.objects.filter(email=data["new_email"]).exists():
                return self.error("The email is owned by other account")
            user.email = data["new_email"]
            user.save()
            return self.success("Succeeded")
        else:
            return self.error("Wrong password")


class UserChangePasswordAPI(APIView):
    @validate_serializer(UserChangePasswordSerializer)
    @login_required
    def post(self, request):
        """
        User change password api
        """
        data = request.data
        username = request.user.username
        user = auth.authenticate(username=username, password=data["old_password"])
        if user:
            if user.two_factor_auth:
                if "tfa_code" not in data:
                    return self.error("tfa_required")
                if not OtpAuth(user.tfa_token).valid_totp(data["tfa_code"]):
                    return self.error("Invalid two factor verification code")
            user.set_password(data["new_password"])
            user.save()
            return self.success("Succeeded")
        else:
            return self.error("Invalid old password")


class ApplyResetPasswordAPI(APIView):
    @validate_serializer(ApplyResetPasswordSerializer)
    def post(self, request):
        if request.user.is_authenticated:
            return self.error("You have already logged in, are you kidding me? ")
        data = request.data
        captcha = Captcha(request)
        if not captcha.check(data["captcha"]):
            return self.error("Invalid captcha")
        try:
            user = User.objects.get(email__iexact=data["email"])
        except User.DoesNotExist:
            return self.error("User does not exist")
        if user.reset_password_token_expire_time and 0 < int(
                (user.reset_password_token_expire_time - now()).total_seconds()) < 20 * 60:
            return self.error("You can only reset password once per 20 minutes")
        user.reset_password_token = rand_str()
        user.reset_password_token_expire_time = now() + timedelta(minutes=20)
        user.save()
        render_data = {
            "username": user.username,
            "website_name": SysOptions.website_name,
            "link": f"{SysOptions.website_base_url}/reset-password/{user.reset_password_token}"
        }
        email_html = render_to_string("reset_password_email.html", render_data)
        send_email(smtp_config=SysOptions.smtp_config,
                   from_name=SysOptions.website_name_shortcut,
                   to_name=user.username,
                   to_email=user.email,
                   subject=f"Reset your password",
                   content=email_html)

        # send_email_async.send(from_name=SysOptions.website_name_shortcut,
        #                       to_email=user.email,
        #                       to_name=user.username,
        #                       subject=f"Reset your password",
        #                       content=email_html)
        return self.success("Succeeded")


class ResetPasswordAPI(APIView):
    @validate_serializer(ResetPasswordSerializer)
    def post(self, request):
        data = request.data
        captcha = Captcha(request)
        if not captcha.check(data["captcha"]):
            return self.error("Invalid captcha")
        try:
            user = User.objects.get(reset_password_token=data["token"])
        except User.DoesNotExist:
            return self.error("Token does not exist")
        if user.reset_password_token_expire_time < now():
            return self.error("Token has expired")
        user.reset_password_token = None
        user.two_factor_auth = False
        user.set_password(data["password"])
        user.save()
        return self.success("Succeeded")


class SessionManagementAPI(APIView):
    @login_required
    def get(self, request):
        engine = import_module(settings.SESSION_ENGINE)
        session_store = engine.SessionStore
        current_session = request.session.session_key
        session_keys = request.user.session_keys
        result = []
        modified = False
        for key in session_keys[:]:
            session = session_store(key)
            # session does not exist or is expiry
            if not session._session:
                session_keys.remove(key)
                modified = True
                continue

            s = {}
            if current_session == key:
                s["current_session"] = True
            s["ip"] = session["ip"]
            s["user_agent"] = session["user_agent"]
            s["last_activity"] = datetime2str(session["last_activity"])
            s["session_key"] = key
            result.append(s)
        if modified:
            request.user.save()
        return self.success(result)

    @login_required
    def delete(self, request):
        session_key = request.GET.get("session_key")
        if not session_key:
            return self.error("Parameter Error")
        request.session.delete(session_key)
        if session_key in request.user.session_keys:
            request.user.session_keys.remove(session_key)
            request.user.save()
            return self.success("Succeeded")
        else:
            return self.error("Invalid session_key")


class UserRankAPI(APIView):
    def get(self, request):
        rule_type = request.GET.get("rule")
        if rule_type not in ContestRuleType.choices():
            rule_type = ContestRuleType.ACM
        profiles = UserProfile.objects.filter(user__admin_type=AdminType.REGULAR_USER, user__is_disabled=False) \
            .select_related("user")
        if rule_type == ContestRuleType.ACM:
            profiles = profiles.filter(submission_number__gt=0).order_by("-accepted_number", "submission_number")
        else:
            profiles = profiles.filter(total_score__gt=0).order_by("-total_score")
        return self.success(self.paginate_data(request, profiles, RankInfoSerializer))


class ProfileProblemDisplayIDRefreshAPI(APIView):
    @login_required
    def get(self, request):
        profile = request.user.userprofile
        acm_problems = profile.acm_problems_status.get("problems", {})
        oi_problems = profile.oi_problems_status.get("problems", {})
        ids = list(acm_problems.keys()) + list(oi_problems.keys())
        if not ids:
            return self.success()
        display_ids = Problem.objects.filter(id__in=ids, visible=True).values_list("_id", flat=True)
        id_map = dict(zip(ids, display_ids))
        for k, v in acm_problems.items():
            v["_id"] = id_map[k]
        for k, v in oi_problems.items():
            v["_id"] = id_map[k]
        profile.save(update_fields=["acm_problems_status", "oi_problems_status"])
        return self.success()


class OpenAPIAppkeyAPI(APIView):
    @login_required
    def post(self, request):
        user = request.user
        if not user.open_api:
            return self.error("OpenAPI function is truned off for you")
        api_appkey = rand_str()
        user.open_api_appkey = api_appkey
        user.save()
        return self.success({"appkey": api_appkey})


class SSOAPI(CSRFExemptAPIView):
    @login_required
    def get(self, request):
        token = rand_str()
        request.user.auth_token = token
        request.user.save()
        return self.success({"token": token})

    @method_decorator(csrf_exempt)
    @validate_serializer(SSOSerializer)
    def post(self, request):
        try:
            user = User.objects.get(auth_token=request.data["token"])
        except User.DoesNotExist:
            return self.error("User does not exist")
        return self.success({"username": user.username, "avatar": user.userprofile.avatar, "admin_type": user.admin_type})
