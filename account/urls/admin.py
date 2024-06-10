from django.conf.urls import url

from ..views.admin import UserAdminAPI, GenerateUserAPI, PublicContInfoAPI

urlpatterns = [
    url(r"^user/?$", UserAdminAPI.as_view(), name="user_admin_api"),
    url(r"^publicContest/?$", PublicContInfoAPI.as_view(), name="Public_Cont_Info_API"),
    url(r"^generate_user/?$", GenerateUserAPI.as_view(), name="generate_user_api"),
]
