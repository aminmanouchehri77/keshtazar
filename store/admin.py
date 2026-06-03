
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from jalali_date.admin import ModelAdminJalaliMixin
from jalali_date import datetime2jalali
from django_jalali.admin.filters import JDateFieldListFilter
from .models import *
from django.urls import path, reverse
from django.shortcuts import redirect


# ------------------- Category Admin -------------------
@admin.register(Category)
class CategoryAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ('title', 'product_count', 'top_product_link')
    search_fields = ('title',)
    list_select_related = ['top_product']
    autocomplete_fields = ['top_product']

    def product_count(self, obj):
        return obj.products.count()

    product_count.short_description = "تعداد محصولات"

    def top_product_link(self, obj):
        if obj.top_product:
            return format_html('<a href="{}">{}</a>',
                               reverse('admin:store_product_change', args=[obj.top_product.id]),
                               obj.top_product.name
                               )
        return "-"

    top_product_link.short_description = "محصول برتر"


# ------------------- Product Admin -------------------
class InventoryFilter(admin.SimpleListFilter):
    title = 'وضعیت موجودی'
    parameter_name = 'inventory_status'

    def lookups(self, request, model_admin):
        return (
            ('low', 'کمتر از ۱۰ عدد'),
            ('normal', '۱۰ تا ۵۰ عدد'),
            ('high', 'بیشتر از ۵۰ عدد'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'low':
            return queryset.filter(inventory__lt=10)
        if self.value() == 'normal':
            return queryset.filter(inventory__range=(10, 50))
        if self.value() == 'high':
            return queryset.filter(inventory__gt=50)


@admin.register(Product)
class ProductAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = (
        'image_preview',
        'name',
        'price_with_discount',
        'inventory_status',
    )
    list_filter = (InventoryFilter, 'category')
    search_fields = ('name', 'manufacturer')
    readonly_fields = ('datetime_modified',)
    autocomplete_fields = ['category']

    # ✅ اکشن‌ها
    actions = [
        'update_inventory',
        'set_inventory_zero',
    ]

    fieldsets = (
        ('اطلاعات پایه', {
            'fields': ('name', 'slug', 'category', 'description', 'image')
        }),
        ('مشخصات فنی', {
            'fields': ('unit_price', 'weight', 'manufacturer', 'inventory')
        }),
        ('دستورالعمل و راهنما', {
            'fields': ('usage_instructions',),
            'classes': ('collapse',)
        }),
        ('تخفیف‌ها و امتیازات', {
            'fields': ('discounts',)
        }),
    )

    # --- فایل JS برای اسلاگ فارسی ---
    class Media:
        js = (
            'admin/js/persian_slugify.js',
        )

    # ---------- نمایش تصویر ----------
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover;" />',
                obj.image.url
            )
        return "-"

    image_preview.short_description = "پیشنمایش"

    # ---------- قیمت با تخفیف ----------
    def price_with_discount(self, obj):
        if obj.discounts:
            return format_html(
                '<del style="color:red;">{}</del> <span>{}</span>',
                obj.unit_price,
                int(obj.unit_price * (1 - obj.discounts.discount))
            )
        return obj.unit_price

    price_with_discount.short_description = "قیمت با تخفیف"

    # ---------- وضعیت موجودی ----------
    def inventory_status(self, obj):
        if obj.inventory < 10:
            color = 'red'
        elif obj.inventory < 50:
            color = 'orange'
        else:
            color = 'green'

        return format_html(
            '<div style="background:{}; color:white; padding:2px 6px; border-radius:4px;">{}</div>',
            color,
            obj.inventory
        )

    inventory_status.short_description = "موجودی"
    inventory_status.admin_order_field = 'inventory'

    # ---------- اکشن افزایش موجودی ----------
    @admin.action(description="➕ افزایش موجودی ۱۰ عددی")
    def update_inventory(self, request, queryset):
        updated_count = queryset.update(
            inventory=models.F('inventory') + 10
        )
        self.message_user(
            request,
            f"✅ موجودی {updated_count} محصول، ۱۰ عدد افزایش یافت."
        )

    # ---------- اکشن صفر کردن موجودی ----------
    @admin.action(description="❌ صفر کردن موجودی محصولات انتخاب‌شده")
    def set_inventory_zero(self, request, queryset):
        updated_count = queryset.update(inventory=0)
        self.message_user(
            request,
            f"⚠️ موجودی {updated_count} محصول با موفقیت صفر شد."
        )


# ------------------- Order Admin -------------------
class OrderItemInline(ModelAdminJalaliMixin, admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('total_price',)
    fields = ('product', 'quantity', 'unit_price', 'total_price')
    autocomplete_fields = ['product']

    def total_price(self, obj):
        try:
            return obj.quantity * obj.unit_price
        except TypeError:
            return 0

    total_price.short_description = "جمع آیتم"


@admin.register(Order)
class OrderAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    jdate_hierarchy = 'datetime_created'
    list_display = (
        'jalali_datetime_created',
        'customer_info',
        'status_badge',
        # 'sent_badge',              # ستون جدید
        'shipping_type',# Badge رنگی
        'total_price_formatted',
        'sent',
        'print_invoice_link',
    )
    list_filter = (
        ('datetime_created', JDateFieldListFilter),
        'status',
        'province',
        'city',
        'sent',                    # اضافه کردن فیلتر ارسال شده
    )
    search_fields = ('mobile', 'postal_code')
    inlines = [OrderItemInline]
    readonly_fields = ('total_price',)

    # --- نمایش تاریخ شمسی ---
    def jalali_datetime_created(self, obj):
        return datetime2jalali(obj.datetime_created).strftime('%Y/%m/%d %H:%M')
    jalali_datetime_created.short_description = "تاریخ ثبت (شمسی)"

    # --- اطلاعات مشتری ---
    def customer_info(self, obj):
        return format_html(
            "{} {}<br>{}",
            obj.first_name,
            obj.last_name,
            obj.mobile
        )
    customer_info.short_description = "مشتری"

    # --- وضعیت پرداخت ---
    def status_badge(self, obj):
        status_info = {
            'p': ('پرداخت شده', 'success'),
            'u': ('پرداخت نشده', 'warning'),
            'c': ('لغو شده', 'danger'),
        }
        text, color = status_info.get(obj.status, ('نامعلوم', 'secondary'))
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            text
        )
    status_badge.short_description = "وضعیت پرداخت"

    # --- وضعیت ارسال ---
    def sent_badge(self, obj):
        if obj.sent:
            return format_html('<span class="badge badge-success">ارسال شده</span>')
        return format_html('<span class="badge badge-secondary">در انتظار ارسال</span>')
    sent_badge.short_description = "وضعیت ارسال"
    sent_badge.admin_order_field = 'sent'

    # --- مبلغ کل قالب‌بندی شده ---
    def total_price_formatted(self, obj):
        return f"{obj.total_price:,} تومان"
    total_price_formatted.short_description = "مبلغ کل"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:order_id>/print-invoice/',
                self.admin_site.admin_view(self._print_invoice),
                name='store_order_print_invoice',
            ),
        ]
        return custom_urls + urls

    def _print_invoice(self, request, order_id, *args, **kwargs):
        # ریدایرکت به view اصلی تولید PDF
        url = reverse('order_invoice_pdf', args=[order_id])
        return redirect(url)

    def print_invoice_link(self, obj):
        url = reverse('admin:store_order_print_invoice', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" target="_blank">📄 چاپ فاکتور</a>',
            url
        )
    print_invoice_link.short_description = 'چاپ فاکتور'
    print_invoice_link.allow_tags = True


# ------------------- Comment Admin -------------------
@admin.register(Comment)
class CommentAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ('product_link', 'user_info', 'status_badge', 'star', 'truncated_body')
    list_filter = ('status', 'star')
    search_fields = ('product__name', 'name__mobile')
    actions = ['approve_comments', 'reject_comments']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'name')

    def product_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:store_product_change', args=[obj.product.id]),
            obj.product.name
        )

    product_link.short_description = "محصول"

    def user_info(self, obj):
        return format_html(
            "{}<br>{}",
            obj.name.get_full_name(),
            obj.name.mobile
        )

    user_info.short_description = "کاربر"

    def truncated_body(self, obj):
        return obj.body[:50] + '...' if len(obj.body) > 50 else obj.body

    truncated_body.short_description = "متن نظر"

    def status_badge(self, obj):
        status_colors = {
            'w': 'secondary',
            'a': 'success',
            'na': 'danger'
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            status_colors.get(obj.status, 'secondary'),
            obj.get_status_display()
        )

    status_badge.short_description = "وضعیت"

    @admin.action(description="تایید نظرات انتخاب‌شده")
    def approve_comments(self, request, queryset):
        queryset.update(status='a')

    @admin.action(description="رد نظرات انتخاب‌شده")
    def reject_comments(self, request, queryset):
        queryset.update(status='na')


# ------------------- Customer Admin -------------------
class AddressInline(ModelAdminJalaliMixin, admin.StackedInline):
    model = Address
    extra = 0


@admin.register(Customer)
class CustomerAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ('full_name', 'phone_number', 'national_code', 'jalali_birth_date')
    search_fields = ('phone_number', 'national_code')
    inlines = [AddressInline]

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    full_name.short_description = "نام کامل"

    def jalali_birth_date(self, obj):
        return datetime2jalali(obj.birth_date).strftime('%Y/%m/%d')
    jalali_birth_date.short_description = "تاریخ تولد (شمسی)"


# ------------------- Other Models -------------------
@admin.register(Discount)
class DiscountAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    # تنظیمات نمایش لیست
    list_display = (
        'code',
        'name',
        'discount_type',
        'discount_value',
        'active_status',
        'time_remaining'
    )
    list_filter = ('discount_code_type', 'start_time')
    search_fields = ('code', 'name')
    ordering = ('-start_time',)
    date_hierarchy = 'start_time'

    # گروه‌بندی فیلدها
    fieldsets = (
        ('اطلاعات پایه', {
            'fields': ('code', 'name')
        }),
        ('تنظیمات تخفیف', {
            'fields': (
                ('discount_code_type', 'discount_code_value'),
            )
        }),
        ('زمان‌بندی', {
            'fields': (
                ('start_time', 'end_time'),
            )
        })
    )

    # نمایش گرافیکی وضعیت
    def active_status(self, obj):
        now = timezone.now()
        if obj.end_time and obj.end_time < now:
            return format_html('<span style="color: red;">⏹ منقضی شده</span>')
        return format_html('<span style="color: green;">⏺ فعال</span>')
    active_status.short_description = 'وضعیت'

    # نمایش زمان باقی‌مانده
    def time_remaining(self, obj):
        if obj.end_time:
            remaining = obj.end_time - timezone.now()
            return f"{remaining.days} روز"
        return "نامحدود"
    time_remaining.short_description = 'زمان باقی‌مانده'

    # تغییر برچسب‌ها
    def discount_type(self, obj):
        return "درصدی" if obj.discount_code_type == "PERCENT" else "مقدار ثابت"
    discount_type.short_description = 'نوع تخفیف'

    def discount_value(self, obj):
        if obj.discount_code_type == "PERCENT":
            return f"{obj.discount_code_value}%"
        return f"{obj.discount_code_value} تومان"
    discount_value.short_description = 'مقدار تخفیف'

    # اعتبارسنجی زمان
    def save_model(self, request, obj, form, change):
        if obj.end_time and obj.end_time < obj.start_time:
            raise ValidationError("تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد")
        super().save_model(request, obj, form, change)


@admin.register(Cart)
class CartAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ('user', 'product', 'quantity')
    # autocomplete_fields = ['user', 'product']
    # search_fields = ('user__mobile', 'product__title')


@admin.register(Faq)
class FaqAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ('question_preview', 'answer_preview')

    def question_preview(self, obj):
        return obj.question[:50] + '...' if len(obj.question) > 50 else obj.question

    question_preview.short_description = "سوال"

    def answer_preview(self, obj):
        return obj.answer[:50] + '...' if len(obj.answer) > 50 else obj.answer

    answer_preview.short_description = "پاسخ"
