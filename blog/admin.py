
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from jalali_date.admin import ModelAdminJalaliMixin

from .models import BlogCategory, BlogArchive, BlogPost, BlogComments


class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'post_count')
    search_fields = ('name',)

    def post_count(self, obj):
        return obj.blogpost_set.count()

    post_count.short_description = 'تعداد پست‌ها'


admin.site.register(BlogCategory, BlogCategoryAdmin)


class BlogArchiveAdmin(admin.ModelAdmin):
    list_display = ('name', 'year_filter')
    search_fields = ('name',)

    def year_filter(self, obj):
        return format_html('<a href="?archive__name__icontains={}">فیلتر بر اساس سال</a>', obj.name)

    year_filter.short_description = 'فیلتر زمانی'


admin.site.register(BlogArchive, BlogArchiveAdmin)


class BlogCommentsInline(ModelAdminJalaliMixin, admin.TabularInline):
    model = BlogComments
    extra = 0
    fields = ('user', 'text_preview', 'status_indicator')
    readonly_fields = ('text_preview', 'status_indicator')

    def text_preview(self, obj):
        return f"{obj.text[:50]}..." if len(obj.text) > 50 else obj.text

    text_preview.short_description = 'پیش‌نمایش نظر'

    def status_indicator(self, obj):
        color = 'green' if obj.is_active else 'red'
        return format_html('<span style="color: {};">●</span>', color)

    status_indicator.short_description = 'وضعیت'


@admin.register(BlogPost)
class BlogPostAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ('title_truncated', 'author', 'status_badge', 'category', 'date_posted_formatted')
    list_filter = ('status', 'category', 'archive', 'date_posted')
    search_fields = ('title', 'text', 'author__mobile')
    inlines = [BlogCommentsInline]
    date_hierarchy = 'date_posted'
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title', 'text', 'text_box', 'image')
        }),
        ('تنظیمات پیشرفته', {
            'fields': ('author', 'category', 'archive', 'status'),
            'classes': ('collapse',)
        }),
    )

    def title_truncated(self, obj):
        return f"{obj.title[:30]}..." if len(obj.title) > 30 else obj.title

    title_truncated.short_description = 'عنوان'

    def date_posted_formatted(self, obj):
        return obj.date_posted.strftime("%Y-%m-%d %H:%M")

    date_posted_formatted.short_description = 'تاریخ انتشار'

    def status_badge(self, obj):
        colors = {'pub': 'green', 'drf': 'orange'}
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 5px;">{}</span>',
            colors[obj.status],
            obj.get_status_display()
        )

    status_badge.short_description = 'وضعیت'


@admin.register(BlogComments)
class BlogCommentsAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = (
        'user', 'post_link', 'text_preview', 'is_active', 'recommended', 'status_indicator', 'recommended_badge')
    list_filter = ('is_active', 'recommended', 'date_posted')
    list_editable = ('is_active', 'recommended')
    search_fields = ('user__mobile', 'text', 'post__title')

    def post_link(self, obj):
        url = reverse("admin:blog_blogpost_change", args=[obj.post.id])
        return format_html('<a href="{}">{}</a>', url, obj.post.title)

    post_link.short_description = 'مطلب مرتبط'

    def text_preview(self, obj):
        return f"{obj.text[:70]}..." if len(obj.text) > 70 else obj.text

    text_preview.short_description = 'متن نظر'

    def status_indicator(self, obj):  # جایگزین status_icon
        icon = '✅' if obj.is_active else '❌'
        color = 'green' if obj.is_active else 'red'
        return format_html('<span style="color: {}; font-size: 1.2em;">{}</span>', color, icon)

    status_indicator.short_description = 'فعال'

    def recommended_badge(self, obj):  # جایگزین recommended_star
        if obj.recommended:
            return format_html(
                '<span style="background: gold; padding: 2px 5px; border-radius: 3px;">⭐ پیشنهادی</span>')
        return ''

    recommended_badge.short_description = 'پیشنهادی'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'post')
