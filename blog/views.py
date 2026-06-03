from django.views import generic
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils.translation import gettext as _
from .models import BlogPost, BlogCategory, BlogArchive
from django.db.models import Q


class BlogPostListView(generic.ListView):
    queryset = BlogPost.objects.select_related('category').filter(status='pub')
    template_name = 'blog/blog_list.html'
    context_object_name = 'posts'
    paginate_by = 4


def post_detail_view(request, pk):
    post = BlogPost.objects.select_related('category', 'archive', 'author').filter(status='pub').get(pk=pk)
    same_posts = BlogPost.objects.filter(status="pub").filter(category=post.category).exclude(
        title=post.title).order_by('pk').reverse()[:6]

    return render(request, 'blog/blog_detail.html', {
        'post_detail': post,
        'same_posts': same_posts,
    })


def post_archive_view(request, pk):

    try:
        archive = BlogArchive.objects.get(pk=pk)
        blogs = BlogPost.objects.filter(archive=archive)
        return render(request, 'blog/blog_archived.html',
                      {'archived_blogs': blogs, 'archive': archive})

    except BlogArchive.DoesNotExist:
        messages.success(request, _('Archive does not exist'))
        return redirect('blog_posts_list')


def post_category_view(request, pk):

    try:
        category = BlogCategory.objects.get(pk=pk)
        blogs = BlogPost.objects.filter(category=category)
        return render(request, 'blog/blog_category.html',
                      {'category': category, 'blogs': blogs, })

    except BlogCategory.DoesNotExist:
        messages.success(request, _('Category does not exist'))
        return redirect('blog_posts_list')


def blogs_search(request):
    word = request.GET.get('search')
    if word is not None:
        blogs_list = BlogPost.objects.filter(Q(title__icontains=word) | Q(text__icontains=word))
        return render(request, 'blog/blog_search.html', {'searched_blogs_list': blogs_list})
    messages.warning(request, _('there is not any blog with this word'))
    return redirect('blog_posts_list')
