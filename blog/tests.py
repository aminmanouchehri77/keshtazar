from django.test import TestCase
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import BlogPost, BlogCategory, BlogArchive
from django.utils.translation import activate

User = get_user_model()


class BlogViewsTest(TestCase):

    def setUp(self):
        # فعال‌سازی زبان پیش‌فرض برای پیام‌ها
        activate('en')

        # ایجاد یک کاربر برای هدایت‌های تست کاربر
        self.user = User.objects.create_user(mobile="09123456789", password="testpassword")

        # ایجاد داده‌های تست
        self.category = BlogCategory.objects.create(name="Test Category")
        self.archive = BlogArchive.objects.create(name="Test Archive")
        self.post = BlogPost.objects.create(
            title="Test Post",
            text="This is a test post.",
            category=self.category,
            author=self.user,
            archive=self.archive,
            status='pub'
        )
        self.client = Client()

    def test_blog_post_list_view(self):
        url = reverse('blog_posts_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'blog/blog_list.html')
        self.assertContains(response, self.post.title)

    def test_post_detail_view(self):
        url = reverse('post_detail', args=[self.post.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'blog/blog_detail.html')
        self.assertContains(response, self.post.title)

    def test_post_archive_view(self):
        url = reverse('post_archive', args=[self.archive.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'blog/blog_archived.html')
        self.assertContains(response, self.archive.name)
        self.assertContains(response, self.post.title)

    def test_post_archive_view_nonexistent(self):
        url = reverse('post_archive', args=[999])
        response = self.client.get(url)
        self.assertRedirects(response, reverse('blog_posts_list'))
        messages = list(response.wsgi_request._messages)
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'Archive does not exist')

    def test_post_category_view(self):
        url = reverse('post_category', args=[self.category.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'blog/blog_category.html')
        self.assertContains(response, self.category.name)
        self.assertContains(response, self.post.title)

    def test_post_category_view_nonexistent(self):
        url = reverse('post_category', args=[999])
        response = self.client.get(url)
        self.assertRedirects(response, reverse('blog_posts_list'))
        messages = list(response.wsgi_request._messages)
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'Category does not exist')

    def test_blogs_search_view_with_results(self):
        url = reverse('blogs_search')
        response = self.client.get(url, {'search': 'Test'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'blog/blog_search.html')
        self.assertContains(response, self.post.title)

    def test_blogs_search_view_without_results(self):
        url = reverse('blogs_search')
        response = self.client.get(url, {'search': 'NonexistentWord'})
        self.assertRedirects(response, reverse('blog_posts_list'))
        messages = list(response.wsgi_request._messages)
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'there is not any blog with this word')



