from django.conf.urls import url
from django.conf import settings
from django.conf.urls.static import static
from ..views.oj import PostCreateView, PostListView, FilteredPostListView, PostDeleteView, PostDetailView, PostUpdateView

urlpatterns = [
    url(r"^", PostListView.as_view(), name = 'forum-home'),
	url(r"filter/", FilteredPostListView.as_view(), name='filtered-home'),
	url(r"post/new/", PostCreateView.as_view(), name = 'post-create'),
	url(r"post/<int:pk>/", PostDetailView.as_view(), name = 'post-detail'),
	url(r"post/<int:pk>/update/", PostUpdateView.as_view(), name = 'post-update'),
	url(r"post/<int:pk>/delete/", PostDeleteView.as_view(), name = 'post-delete'),
	url(r"post/<int:pk>/comment/", views.add_comment_to_post, name='add_comment_to_post'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)