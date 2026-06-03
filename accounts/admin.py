from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # تنظیمات نمایش لیست کاربران
    list_display = ('mobile', 'otp_status', 'otp_create_time_formatted')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    search_fields = ('mobile', 'otp')
    ordering = ('-otp_create_time',)

    # تنظیمات فرم ویرایش
    fieldsets = (
        (None, {'fields': ('mobile', 'password')}),
        ('مجوزها', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('OTP', {'fields': ('otp', 'otp_create_time')}),
    )

    # غیرفعال کردن فیلدهای غیرقابل ویرایش
    readonly_fields = ('otp_create_time',)

    # فرمت‌دهی زمان ایجاد OTP
    def otp_create_time_formatted(self, obj):
        return obj.otp_create_time.strftime("%Y-%m-%d %H:%M:%S")

    otp_create_time_formatted.short_description = "زمان ایجاد OTP"

    # نمایش وضعیت OTP
    def otp_status(self, obj):
        if obj.otp:
            return format_html('<span style="color: green;">✅ فعال</span>')
        return format_html('<span style="color: red;">❌ غیرفعال</span>')

    otp_status.short_description = "وضعیت OTP"

    # حذف فیلد username از فرم
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        return [fieldset for fieldset in fieldsets if fieldset[0] != 'Username']
