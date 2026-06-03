from .models import BlogCategory, BlogPost, BlogArchive


def category_view(request):
    return {'blog_categories': BlogCategory.objects.all()}


def latest_posts(request):
    return {'blog_latest_posts': BlogPost.objects.filter(status='pub').order_by('date_posted').reverse()[:4]}


def archive_posts(request):
    return {'archives': BlogArchive.objects.all().reverse()[:6]}


