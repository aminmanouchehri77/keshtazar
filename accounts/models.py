
from django.contrib.auth.models import AbstractUser
from accounts.myusermanager import MyUserManager
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    username = None  # حذف فیلد نام کاربری پیش‌فرض
    mobile = models.CharField(
        max_length=11,
        unique=True,
        verbose_name="شماره موبایل"
    )
    otp = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="کد یکبار مصرف"
    )
    otp_create_time = models.DateTimeField(
        auto_now=True,
        verbose_name="زمان ایجاد OTP"
    )

    objects = MyUserManager()

    USERNAME_FIELD = 'mobile'
    REQUIRED_FIELDS = []

    backend = 'accounts.my_modelbackends.MobileBackend'

    class Meta:
        verbose_name = "کاربر سفارشی"
        verbose_name_plural = "کاربران سفارشی"


class AdminProfile(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        verbose_name='کاربر'
    )
    last_visit = models.DateTimeField(
        default=timezone.now,
        verbose_name='آخرین بازدید'
    )

    class Meta:
        verbose_name = 'پروفایل مدیر'
        verbose_name_plural = 'پروفایل‌های مدیران'

    def __str__(self):
        return f"{self.user.mobile} - آخرین بازدید: {self.last_visit}"

    def update_last_visit(self):
        self.last_visit = timezone.now()
        self.save(update_fields=['last_visit'])
