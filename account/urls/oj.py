from django.conf.urls import url

from ..views.oj import (ApplyResetPasswordAPI, ResetPasswordAPI,
                        TokenAuthenticationAPI, TokenRefreshAPI,
                        UserChangePasswordAPI, UserRegisterAPI, UserChangeEmailAPI,
                        UserLoginAPI, UserLogoutAPI, UsernameOrEmailCheck,
                        AvatarUploadAPI, TwoFactorAuthAPI, UserProfileAPI,
                        UserRankAPI, CheckTFARequiredAPI, SessionManagementAPI,getPublicKeyAPI,
                        ProfileProblemDisplayIDRefreshAPI, OpenAPIAppkeyAPI, SSOAPI, SchoolssnCheck, UserProgress)

from utils.captcha.views import CaptchaAPIView

urlpatterns = [
    url(r"^token_auth/?$", TokenAuthenticationAPI.as_view(), name="token_authentication_api"),
    url(r"^token_refresh/?$", TokenRefreshAPI.as_view(), name="token_refresh_api"),
    url(r"^login/?$", UserLoginAPI.as_view(), name="user_login_api"),
    url(r"^logout/?$", UserLogoutAPI.as_view(), name="user_logout_api"),
    url(r"^register/?$", UserRegisterAPI.as_view(), name="user_register_api"),
    url(r"^change_password/?$", UserChangePasswordAPI.as_view(), name="user_change_password_api"),
    url(r"^change_email/?$", UserChangeEmailAPI.as_view(), name="user_change_email_api"),
    url(r"^apply_reset_password/?$", ApplyResetPasswordAPI.as_view(), name="apply_reset_password_api"),
    url(r"^reset_password/?$", ResetPasswordAPI.as_view(), name="reset_password_api"),
    url(r"^captcha/?$", CaptchaAPIView.as_view(), name="show_captcha"),
    url(r"^check_username_or_email", UsernameOrEmailCheck.as_view(), name="check_username_or_email"),
    url(r"^check_schoolssc", SchoolssnCheck.as_view(), name="check_schoolssn"),
    url(r"^profile/?$", UserProfileAPI.as_view(), name="user_profile_api"),
    url(r"^profile/fresh_display_id", ProfileProblemDisplayIDRefreshAPI.as_view(), name="display_id_fresh"),
    url(r"^upload_avatar/?$", AvatarUploadAPI.as_view(), name="avatar_upload_api"),
    url(r"^tfa_required/?$", CheckTFARequiredAPI.as_view(), name="tfa_required_check"),
    url(r"^two_factor_auth/?$", TwoFactorAuthAPI.as_view(), name="two_factor_auth_api"),
    url(r"^user_rank/?$", UserRankAPI.as_view(), name="user_rank_api"),
    url(r"^sessions/?$", SessionManagementAPI.as_view(), name="session_management_api"),
    url(r"^open_api_appkey/?$", OpenAPIAppkeyAPI.as_view(), name="open_api_appkey_api"),
    url(r"^sso?$", SSOAPI.as_view(), name="sso_api"),
    url(r"^userprogress?$", UserProgress.as_view(), name="userprogress_api"),
    url(r"^get_public_key/?$", getPublicKeyAPI.as_view(), name="get_public_key_api")
]
