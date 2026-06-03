from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class BlogCategory(models.Model):
    class Meta:
        verbose_name = "دسته‌بندی وبلاگ"
        verbose_name_plural = "دسته‌بندی‌های وبلاگ"

    name = models.CharField(max_length=20, verbose_name="نام دسته‌بندی")

    def __str__(self):
        return self.name


class BlogArchive(models.Model):
    class Meta:
        verbose_name = "آرشیو وبلاگ"
        verbose_name_plural = "آرشیوهای وبلاگ"

    name = models.CharField(max_length=20, verbose_name="نام آرشیو")

    def __str__(self):
        return self.name


class BlogPost(models.Model):
    class Meta:
        verbose_name = "پست وبلاگ"
        verbose_name_plural = "پست‌های وبلاگ"

    STATUS_CHOICES = (
        ('pub', 'منتشر شده'),
        ('drf', 'پیش‌نویس')
    )

    title = models.CharField(verbose_name="عنوان", max_length=100)
    text = models.TextField(verbose_name="متن")
    text_box = models.CharField(verbose_name="متن برجسته", max_length=100, blank=True)
    author = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        verbose_name="نویسنده"
    )
    category = models.ForeignKey(
        'BlogCategory',
        on_delete=models.CASCADE,
        verbose_name="دسته‌بندی",
        null=True
    )
    image = models.ImageField(
        verbose_name="تصویر",
        upload_to='pages/blogpost/',
        blank=True
    )
    status = models.CharField(
        verbose_name="وضعیت",
        choices=STATUS_CHOICES,
        max_length=10
    )
    archive = models.ForeignKey(
        'BlogArchive',
        on_delete=models.CASCADE,
        verbose_name="آرشیو",
        null=True
    )
    date_posted = models.DateTimeField(
        verbose_name="تاریخ ایجاد",
        default=timezone.now
    )
    date_updated = models.DateTimeField(
        verbose_name="تاریخ بروزرسانی",
        auto_now=True
    )

    def __str__(self):
        return f"عنوان: {self.title} | نویسنده: {self.author} | وضعیت: {self.status}"

    def get_absolute_url(self):
        return reverse('blog_post_detail', args=[self.id])


class BlogComments(models.Model):
    class Meta:
        verbose_name = "نظر وبلاگ"
        verbose_name_plural = "نظرات وبلاگ"

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        verbose_name="کاربر"
    )
    text = models.TextField(verbose_name="متن نظر")
    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name="پست"
    )
    email = models.EmailField(verbose_name="ایمیل", blank=True)
    site = models.URLField(verbose_name="وب‌سایت", null=True, blank=True)
    date_posted = models.DateTimeField(verbose_name="تاریخ ارسال", default=timezone.now)
    is_active = models.BooleanField(verbose_name="فعال بودن", default=True)
    recommended = models.BooleanField(verbose_name="پیشنهاد شده", default=False)

    def __str__(self):
        return f'{self.user}: {self.text}'