from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.conf import settings
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from config import DiscountType
from slugify import slugify as unicode_slugify
from ckeditor.fields import RichTextField
from django.db.models import JSONField, F


class Category(models.Model):
    class Meta:
        verbose_name = "دسته‌بندی محصول"
        verbose_name_plural = "دسته‌بندی‌های محصولات"

    title = models.CharField(
        max_length=255,
        verbose_name="عنوان"
    )
    description = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="توضیحات"
    )
    top_product = models.ForeignKey(
        'Product',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='+',
        verbose_name="محصول برتر"
    )

    def __str__(self):
        return self.title


class DiscountManager(models.Manager):
    def active(self):
        """فیلتر تخفیف‌های فعال با توجه به زمان شروع و پایان"""
        date = timezone.now()
        return self.filter(Q(end_time__isnull=True) | Q(end_time__gte=date), start_time__lte=date)


class Discount(models.Model):
    class Meta:
        verbose_name = "تخفیف"
        verbose_name_plural = "تخفیف‌ها"

    code = models.CharField(
        max_length=100,
        verbose_name="کد تخفیف"
    )
    name = models.CharField(
        max_length=255,
        verbose_name="نام تخفیف"
    )
    start_time = models.DateTimeField(
        default=timezone.now,
        verbose_name="زمان شروع"
    )
    end_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان پایان"
    )
    discount_code_type = models.CharField(
        max_length=7,
        choices=DiscountType.CHOICES,
        default=DiscountType.FIXED,
        verbose_name="نوع تخفیف"
    )
    discount_code_value = models.PositiveIntegerField(
        verbose_name="مقدار تخفیف"
    )

    objects = DiscountManager()

    def __str__(self):
        return self.name

    def get_discount(self, price):
        """محاسبه مبلغ محصول پس از اعمال تخفیف"""
        if self.discount_code_type == DiscountType.FIXED:
            return max(price - self.discount_code_value, 0)

        percent = int(price * (self.discount_code_value / 100))
        return max(price - percent, 0)


class DiscountUsage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="کاربر"
    )  # کاربر
    discount = models.ForeignKey(
        Discount,
        on_delete=models.CASCADE,
        verbose_name="کد تخفیف"
    )  # کد تخفیف
    order = models.ForeignKey(
        'Order',
        on_delete=models.CASCADE,
        related_name='discount_usages',
        verbose_name="سفارش"
    )  # سفارش مربوطه
    used_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="زمان استفاده"
    )  # زمان استفاده از کد

    class Meta:
        verbose_name = "استفاده از تخفیف"
        verbose_name_plural = "استفاده‌های تخفیف"
        unique_together = ('user', 'discount')  # اطمینان از اینکه هر کاربر فقط یکبار از هر کد تخفیف استفاده کند

    def __str__(self):
        return f"User {self.user} used {self.discount} on Order {self.order.id}"


class Product(models.Model):
    class Meta:
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"

    # گزینه‌های مربوط به امتیاز محصول
    STAR_STATUS_BAD = 'b'
    STAR_STATUS_NOT_BAD = 'nb'
    STAR_STATUS_GOOD = 'g'
    STAR_STATUS_VERY_GOOD = 'v'
    STAR_STATUS_EXCELLENT = 'e'
    STAR_STATUS = [
        (STAR_STATUS_BAD, 'ضعیف'),
        (STAR_STATUS_NOT_BAD, 'قابل قبول'),
        (STAR_STATUS_GOOD, 'خوب'),
        (STAR_STATUS_VERY_GOOD, 'خیلی خوب'),
        (STAR_STATUS_EXCELLENT, 'عالی'),
    ]

    name = models.CharField(
        max_length=255,
        verbose_name="نام محصول"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name="دسته‌بندی"
    )
    slug = models.SlugField(
        verbose_name="اسلاگ",
        allow_unicode=True,  # فعال کردن یونیکد برای SlugField
        blank=True
    )
    description = RichTextField(
        verbose_name="توضیحات"
    )
    usage_instructions = RichTextField(
        verbose_name="دستورالعمل مصرف",
        null=True,
        blank=True,
        default="_"
    )
    image = models.ImageField(
        upload_to='pages/store/',
        null=True,
        blank=True,
        verbose_name="تصویر"
    )
    unit_price = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name="قیمت واحد"
    )
    weight = models.CharField(
        max_length=255,
        null=True,
        verbose_name="وزن/حجم"
    )
    manufacturer = models.CharField(
        max_length=255,
        null=True,
        verbose_name="تولیدکننده"
    )
    inventory = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name="موجودی"
    )
    datetime_created = models.DateTimeField(
        default=timezone.now,
        verbose_name="تاریخ ایجاد"
    )
    datetime_modified = models.DateTimeField(
        auto_now=True,
        verbose_name="تاریخ آخرین ویرایش"
    )
    discounts = models.ForeignKey(
        Discount,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        default=None,
        verbose_name="تخفیف"
    )

    def is_available(self):
        """بررسی موجودی محصول"""
        return self.inventory > 0

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        """ایجاد لینک برای دسترسی به صفحه جزئیات محصول"""
        return reverse('product_detail', kwargs={'pk': self.pk})

    def save(self, *args, **kwargs):
        if not self.slug:
            # یا استفاده از کتابخانه python-slugify (توصیه شده)
            self.slug = unicode_slugify(self.name, allow_unicode=True)

        super().save(*args, **kwargs)


class Customer(models.Model):
    class Meta:
        verbose_name = "مشتری"
        verbose_name_plural = "مشتری‌ها"

    phone_number = models.OneToOneField(
        get_user_model(),
        on_delete=models.PROTECT,
        verbose_name="شماره موبایل"
    )
    first_name = models.CharField(
        max_length=30,
        verbose_name="نام"
    )
    last_name = models.CharField(
        max_length=30,
        verbose_name="نام خانوادگی"
    )
    email = models.EmailField(
        null=True,
        blank=True,
        verbose_name="ایمیل"
    )
    national_code = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="کد ملی"
    )
    birth_date = models.DateField(

        verbose_name="تاریخ تولد"
    )

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class Address(models.Model):
    class Meta:
        verbose_name = "آدرس مشتری"
        verbose_name_plural = "آدرس‌های مشتری‌ها"

    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        primary_key=True,
        verbose_name="مشتری"
    )
    province = models.CharField(
        max_length=255,
        verbose_name="استان"
    )
    city = models.CharField(
        max_length=255,
        verbose_name="شهر"
    )
    street = models.CharField(
        max_length=255,
        verbose_name="خیابان"
    )
    postal_code = models.CharField(
        max_length=10,
        verbose_name="کد پستی"
    )

    def __str__(self):
        return f'{self.province} {self.city} خیابان {self.street}'


class UnpaidOrderManger(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status=Order.ORDER_STATUS_UNPAID)


class Order(models.Model):
    class Meta:
        verbose_name = "سفارشات"

    ORDER_STATUS_PAID = 'p'
    ORDER_STATUS_UNPAID = 'u'
    ORDER_STATUS_CANCELED = 'c'
    ORDER_STATUS = [
        (ORDER_STATUS_PAID, 'پرداخت شده'),
        (ORDER_STATUS_UNPAID, 'پرداخت نشده'),
        (ORDER_STATUS_CANCELED, 'لغو شده'),
    ]
    SHIPPING_METHODS = [
        ('tipax', 'تیپاکس (پس کرایه + ۳۰٬۰۰۰ تومان)'),
        ('freight', 'باربری (پس کرایه + ۳۰٬۰۰۰ تومان)'),
        ('city', 'درون‌شهری (رایگان)'),
        ('pickup', 'تحویل حضوری (رایگان)'),
    ]
    mobile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders', verbose_name="شماره تماس")
    datetime_created = models.DateTimeField(default=timezone.now, verbose_name="تاریخ ثبت")
    status = models.CharField(max_length=1, choices=ORDER_STATUS, default=ORDER_STATUS_UNPAID, verbose_name="وضعیت سفارش")
    total_price = models.IntegerField(verbose_name="قیمت کل")
    discount_code = models.CharField(max_length=100, null=True, blank=True, verbose_name="کد تخفیف")  # کد تخفیف وارد# شده
    discount = models.ForeignKey(Discount, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="تخفیف")
    first_name = models.CharField(max_length=50, verbose_name="نام")
    last_name = models.CharField(max_length=50, verbose_name="نام خانوادگی")
    address = models.TextField(verbose_name="آدرس")
    province = models.CharField(max_length=500, verbose_name="استان")
    city = models.CharField(max_length=500, verbose_name="شهر")
    postal_code = models.CharField(max_length=10, verbose_name='کدپستی')
    note = models.TextField(blank=True, verbose_name='توضیحات')
    shipping_type = models.CharField(
        max_length=20,
        choices=SHIPPING_METHODS,
        default='pickup',
        verbose_name='نوع ارسال'
    )
    # zarinpal_authority = models.CharField(max_length=50, null=True)
    # zarinpal_ref_id = models.CharField(max_length=50, blank=True, null=True)
    sep_token = models.CharField(
        max_length=128,
        null=True, blank=True,
        verbose_name='توکن SEP'
    )
    sep_refnum = models.CharField(
        max_length=50,
        null=True, blank=True,
        verbose_name='شماره پیگیری (RefNum) SEP'
    )
    sep_payment_data = JSONField(
        null=True, blank=True,
        verbose_name='داده‌های Callback SEP'
    )
    payment_data = models.TextField(blank=True, null=True, verbose_name="اطلاعات سفارش")
    inventory_deducted = models.BooleanField(default=False, verbose_name="کاهش موجودی")
    sent = models.BooleanField(
        default=False,
        verbose_name="ارسال شده"
    )

    objects = models.Manager()
    unpaid_orders = UnpaidOrderManger()

    def __str__(self):
        return f'Order id={self.id}'


class OrderItem(models.Model):
    class Meta:
        unique_together = [['order', 'product']]
        verbose_name = "آیتم های سفارشات"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items')
    quantity = models.PositiveSmallIntegerField(default=1)
    unit_price = models.IntegerField()

    def __str__(self):
        return f'OrderItem {self.id}: {self.product} x {self.quantity} (price:{self.unit_price})'


class CommentManager(models.Manager):
    """
    مدیریت کلیه نظرات
    """

    def get_approved(self):
        """فیلتر نظرات تایید شده"""
        return self.get_queryset().filter(status=Comment.COMMENT_STATUS_APPROVED)


class ApprovedCommentManager(models.Manager):
    """
    مدیریت نظرات تایید شده
    """

    def get_queryset(self):
        """بازگشت فقط نظرات تایید شده"""
        return super().get_queryset().filter(status=Comment.COMMENT_STATUS_APPROVED)


class Comment(models.Model):
    """
    مدل نظرات برای محصولات
    """

    class Meta:
        verbose_name = "نظر محصول"
        verbose_name_plural = "نظرات محصولات"

    # وضعیت نظرات
    COMMENT_STATUS_WAITING = 'w'
    COMMENT_STATUS_APPROVED = 'a'
    COMMENT_STATUS_NOT_APPROVED = 'na'
    COMMENT_STATUS = [
        (COMMENT_STATUS_WAITING, 'در انتظار تایید'),
        (COMMENT_STATUS_APPROVED, 'تایید شده'),
        (COMMENT_STATUS_NOT_APPROVED, 'تایید نشده'),
    ]

    # وضعیت امتیازدهی
    STAR_STATUS_BAD = '1'
    STAR_STATUS_NOT_BAD = '2'
    STAR_STATUS_GOOD = '3'
    STAR_STATUS_VERY_GOOD = '4'
    STAR_STATUS_EXCELLENT = '5'
    STAR_STATUS = [
        (STAR_STATUS_BAD, 'ضعیف'),
        (STAR_STATUS_NOT_BAD, 'قابل قبول'),
        (STAR_STATUS_GOOD, 'خوب'),
        (STAR_STATUS_VERY_GOOD, 'خیلی خوب'),
        (STAR_STATUS_EXCELLENT, 'عالی'),
    ]

    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name="محصول"
    )
    name = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="کاربر"
    )
    body = models.TextField(
        verbose_name="متن نظر"
    )
    datetime_created = models.DateTimeField(
        default=timezone.now,
        verbose_name="تاریخ ایجاد"
    )
    status = models.CharField(
        max_length=2,
        choices=COMMENT_STATUS,
        default=COMMENT_STATUS_WAITING,
        verbose_name="وضعیت"
    )
    star = models.CharField(
        max_length=2,
        choices=STAR_STATUS,
        default=STAR_STATUS_EXCELLENT,
        verbose_name="امتیاز"
    )

    # مینیجرهای سفارشی
    objects = CommentManager()
    approved = ApprovedCommentManager()

    def __str__(self):
        return f"{self.name} - {self.product.name}: {self.body[:30]}..."


class Cart(models.Model):
    """
    مدل سبد خرید
    """

    class Meta:
        unique_together = [['user', 'product']]
        verbose_name = "سبد خرید"
        verbose_name_plural = "سبدهای خرید"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="کاربر"
    )
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='cart_items',
        verbose_name="محصول"
    )
    quantity = models.PositiveSmallIntegerField(
        verbose_name="تعداد"
    )


class Faq(models.Model):
    """
    مدل سوالات متداول
    """

    class Meta:
        verbose_name = "سوال متداول"
        verbose_name_plural = "سوالات متداول"

    question = models.TextField(
        verbose_name="سوال"
    )
    answer = models.TextField(
        verbose_name="پاسخ"
    )
