from django.urls import re_path

from ..views.admin import UserAdminAPI, GenerateUserAPI, PublicContInfoAPI, UserLoginStatsAPI

urlpatterns = [
    re_path(r"^user/?$", UserAdminAPI.as_view(), name="user_admin_api"),
    re_path(r"^publicContest/?$", PublicContInfoAPI.as_view(), name="Public_Cont_Info_API"),
    re_path(r"^generate_user/?$", GenerateUserAPI.as_view(), name="generate_user_api"),
    re_path(r"^userloginstats/?$", UserLoginStatsAPI.as_view(), name="userlogin_counts_api"),
]
