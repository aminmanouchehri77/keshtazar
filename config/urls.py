"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.conf.urls.static import static
from debug_toolbar.toolbar import debug_toolbar_urls

import accounts
from config import settings
from store.views import services_view, contact_us_view, index_view
from .sitemap import BlogPostSitemap, ProductSitemap, CategorySitemap, FaqSitemap, StaticViewSitemap

sitemaps = {
    'blogposts': BlogPostSitemap,
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'faqs': FaqSitemap,
    'static': StaticViewSitemap,
}

urlpatterns = [
    path('keshtazaradmin/', admin.site.urls),
    path('blog/', include('blog.urls')),
    path('store/', include('store.urls')),
    path('rosetta/', include('rosetta.urls')),
    path('', index_view, name='index'),
    path('accounts/', include('accounts.urls')),
    path('services/', services_view, name='services'),
    path('contact_us/', contact_us_view, name='contact_us'),
    path('ckeditor/', include('ckeditor_uploader.urls')),  # اضافه کردن مسیر CKEditor
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    )
]

# اضافه کردن مسیرهای مدیا فقط در محیط توسعه
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += debug_toolbar_urls()
else:
    # در محیط تولید نیز فایل‌های مدیا را سرو کنید
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = 'پنل مدیریتی فروشگاه کشت آذر'
admin.site.site_title = 'فروشگاه کشت آذر پاسارگاد'
admin.site.index_title = 'فروشگاه کشت آذر پاسارگاد'
