from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from blog.models import BlogPost
from store.models import Product, Category, Faq


# Sitemap برای پست‌های وبلاگ
class BlogPostSitemap(Sitemap):
    changefreq = "weekly"  # دفعات به‌روزرسانی صفحه
    priority = 0.8  # اولویت صفحه

    def items(self):
        # فقط پست‌های منتشر شده را در سایت مپ قرار دهید
        return BlogPost.objects.filter(status='pub')

    def lastmod(self, obj):
        # تاریخ آخرین بروزرسانی پست
        return obj.date_updated


class ProductSitemap(Sitemap):
    changefreq = "weekly"  # تغییرات هفته‌ای
    priority = 0.8         # اهمیت URL

    def items(self):
        # فقط محصولات موجود نمایش داده شوند
        return Product.objects.filter(inventory__gt=0)

    def lastmod(self, obj):
        return obj.datetime_modified


class CategorySitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return Category.objects.all()

    def location(self, obj):
        # اگر URL مشخص برای دسته‌بندی وجود ندارد، یک مقدار ثابت یا قابل محاسبه بازگردانید
        return f"/category/{obj.pk}/"


class FaqSitemap(Sitemap):
    changefreq = "yearly"
    priority = 0.3

    def items(self):
        return Faq.objects.all()

    def location(self, obj):
        # بازگرداندن URL ثابت یا محاسبه‌شده برای هر سوال متداول
        return f"/faq/{obj.pk}/"


class StaticViewSitemap(Sitemap):
    changefreq = "monthly"  # تغییرات ماهانه یا never
    priority = 0.5  # اولویت متوسط برای صفحات ثابت

    def items(self):
        # نام‌های URLهای ثابت را بازگردانید
        return ['contact_us', 'services']

    def location(self, item):
        # URL مربوط به هر نام مسیر را بازگردانید
        return reverse(item)
