from django.contrib import admin
from django.urls import path, include
from . views import BlogPostListView, post_detail_view, post_category_view, post_archive_view, blogs_search


urlpatterns = [
    path('', BlogPostListView.as_view(), name='blog_posts_list'),
    path('<int:pk>/', post_detail_view, name='blog_post_detail'),
    path('category/<int:pk>/', post_category_view, name='blog_category'),
    path('archive/<int:pk>/', post_archive_view, name='blog_archive'),
    path('search/', blogs_search, name='blog_search')

]
