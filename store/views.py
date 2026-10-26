import logging
import io
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg
from django.db.models import F
from django.db.models import Prefetch, FloatField
from django.db.models.functions import Cast
from django.http import Http404
from django.shortcuts import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView
from django.views.generic import TemplateView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db import transaction
from weasyprint import HTML

from blog.models import BlogPost
from config import settings
from store.models import Category, Comment, Faq, Customer, OrderItem, Address, Discount, DiscountUsage
from .models import Order, OrderItem, Cart, Product
from .utils import SEPPayment, send_kavenegar  # کلاس کمکی SEP
from .cart import Cart, CART_SESSION_ID  # اضافه کردن import برای کلاس Cart و CART_SESSION_ID
from .forms import CommentForm, CustomerForm, AddressForm
from .models import Order
from .models import Product, Cart as CartModel  # اضافه کردن import برای مدل Cart
from .utils import save_order, get_or_create_order_for_user
from django.template.loader import render_to_string
from django.http import HttpResponse
from xhtml2pdf import pisa
from .models import Order
from jalali_date import datetime2jalali
from django.template.loader import get_template


logger = logging.getLogger(__name__)


def store_products_list_view(request):
    # استفاده از Prefetch برای مرتب‌سازی محصولات هر دسته بر اساس موجودی (از زیاد به کم)
    category = Category.objects.prefetch_related(
        Prefetch(
            'products',
            queryset=Product.objects.order_by('-inventory')  # مرتب‌سازی محصولات هر دسته بر اساس موجودی
        )
    ).all()[:8]

    # دریافت همه محصولات و مرتب‌سازی آنها بر اساس موجودی از زیاد به کم
    all_products = Product.objects.order_by('-inventory')

    return render(request, "store/shop.html", context={
        'category_list': category,
        'all_products': all_products
    })


def products_details_view(request, pk, slug):
    product = get_object_or_404(
        Product.objects.filter(slug=slug),
        pk=pk
    )
    error_message = ''
    has_purchased = False
    average_rating = 0

    # دریافت کامنت‌های تایید شده
    approved_comments = product.comments.filter(
        status=Comment.COMMENT_STATUS_APPROVED
    ).order_by('-datetime_created')

    # محاسبه میانگین امتیاز
    if approved_comments.exists():
        avg_result = approved_comments.annotate(
            numeric_star=Cast('star', FloatField())
        ).aggregate(average=Avg('numeric_star'))

        average_rating = round(avg_result['average'], 1) if avg_result['average'] else 0

    if request.user.is_authenticated:
        # بررسی خرید کاربر
        has_purchased = OrderItem.objects.filter(
            order__mobile=request.user,
            order__status=Order.ORDER_STATUS_PAID,
            product=product
        ).exists()

    # پردازش فرم کامنت
    if request.method == "POST":
        if not request.user.is_authenticated:
            error_message = "برای ثبت نظر باید وارد حساب کاربری خود شوید"
        elif not has_purchased:
            error_message = "برای ثبت نظر باید این محصول را خریداری کرده باشید"
        else:
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                new_comment = comment_form.save(commit=False)
                new_comment.product = product
                new_comment.name = request.user
                new_comment.status = Comment.COMMENT_STATUS_WAITING
                new_comment.save()
                # افزودن پیام موفقیت
                messages.success(
                    request,
                    "✅ نظر شما با موفقیت ثبت شد و پس از بررسی نمایش داده خواهد شد"
                )
                return redirect('product_detail', pk=product.pk, slug=product.slug)
            else:
                error_message = "لطفا اطلاعات فرم را به درستی وارد کنید"
        comment_form = CommentForm(request.POST)
    else:
        comment_form = CommentForm()

    context = {
        'product': product,
        'comment_form': comment_form,
        'apro_comments': approved_comments,
        'average_rating': average_rating,
        'error_message': error_message,
        'has_purchased': has_purchased,
    }
    return render(request, 'store/product_detail.html', context)


def faq_view(request):
    faqs = Faq.objects.all()
    return render(request, "store/faq.html", context={'faqs': faqs})


def services_view(request):
    return render(request, 'services.html')


def contact_us_view(request):
    return render(request, 'contact_us.html')


def index_view(request):
    categories = Category.objects.prefetch_related(Prefetch(
        'products',
        queryset=Product.objects.order_by('-inventory')
    )).all()[:8]
    for category in categories:
        category.limited_products = category.products.all()[:8]

    # Add this line to get all products sorted by inventory
    all_products = Product.objects.all().order_by('-inventory')[:8]

    faqs = Faq.objects.all()[:4]
    blogs = BlogPost.objects.select_related('category').filter(status='pub').order_by('-date_posted')[:3]
    if len(blogs) == 0:
        blog1 = blogs
        blog2 = blogs
        blog3 = blogs
    elif len(blogs) == 1:
        blog1 = blogs[0]
        blog2 = blogs
        blog3 = blogs
    elif len(blogs) == 2:
        blog1 = blogs[0]
        blog2 = blogs[1]
        blog3 = blogs
    else:
        blog1 = blogs[0]
        blog2 = blogs[1]
        blog3 = blogs[2]

    return render(request, 'index.html', context={
        'category_list_i': categories,
        'faqs': faqs,
        'blog1': blog1,
        'blog2': blog2,
        'blog3': blog3,
        'all_products': all_products,  # Add this line to include all products in the context
    })


def products_search_view(request):
    word = request.GET.get('search')
    products_list = Product.objects.filter(name__icontains=word)
    return render(request, 'store/products_search.html', {'searched_products_list': products_list})


def add_to_cart(request):
    product_id = request.POST.get('product_id')
    quantity = request.POST.get('quantity')
    update = True if request.POST.get('update1') == "1" else False
    active_tab = request.POST.get('active_tab', 0)  # Get active_tab, default to 0

    # دریافت محصول
    product = get_object_or_404(Product, id=product_id)

    # اضافه کردن به سبد خرید
    cart_object = Cart.get_cart(request)
    cart_object.add(product_id, str(product.unit_price), int(quantity), update)

    # ایجاد پیام موفقیت
    product_name = product.title if hasattr(product, 'title') else product.name
    success_message = f"{quantity} عدد {product_name} به سبد خرید شما اضافه شد."

    # محاسبه تعداد آیتم‌های سبد خرید
    cart_count = 0
    if request.user.is_authenticated:
        cart_count = sum(item.quantity for item in CartModel.objects.filter(user_id=request.user.id))
    else:
        cart_session = request.session.get(CART_SESSION_ID, {})
        cart_count = sum(item['quantity'] for item in cart_session.values())

    # بررسی اگر درخواست AJAX است
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # برگرداندن پاسخ JSON برای درخواست‌های AJAX
        return JsonResponse({
            'status': 'success',
            'message': success_message,
            'cart_count': cart_count
        })
    else:
        # برای درخواست‌های غیر AJAX، پیام موفقیت را به سیستم پیام‌رسانی اضافه کنید
        messages.success(request, success_message)

        # ریدایرکت به صفحه قبلی (یا صفحه محصول)
        referer = request.META.get('HTTP_REFERER')
        if referer:
            # Append the active_tab to the referer URL
            if '?' in referer:
                redirect_url = f"{referer}&tab={active_tab}"
            else:
                redirect_url = f"{referer}?tab={active_tab}"
            return redirect(redirect_url)
        else:
            # اگر referer موجود نبود، به صفحه اصلی برگردید
            return redirect(reverse('index') + f'?tab={active_tab}')


def cart_detail_view(request):
    return render(request, 'store/cart.html')


def remove_from_cart(request, product_id):
    if Product.objects.filter(id=product_id).exists():
        cart_object = Cart.get_cart(request)
        cart_object.remove(str(product_id))
        return redirect(reverse('cart_detail'))
    raise Http404('product not found')


@login_required
def checkout_view(request):
    try:
        Customer.objects.get(phone_number=request.user)
    except Customer.DoesNotExist:
        return redirect(reverse('profile'))
    cart = Cart.get_cart(request)
    for item in cart:
        product = item['product']
        if item['quantity'] > product.inventory:
            messages.error(request,
                           f"تعداد انتخاب شده بیش از موجودی محصول  {product.name} در انبار است!  ")
            return redirect('cart_detail')
    if request.method == 'POST':
        shipping_type = request.POST.get('shipping_type') or request.session.get('shipping_type')
        order = save_order(cart, request, shipping_type=shipping_type)
        return redirect(reverse('payment_process', args=[order.id]))

    return render(request, 'store/checkout.html')


def profile_view(request):
    if request.method == "POST":
        customer_form = CustomerForm(request.POST)
        address_form = AddressForm(request.POST)

        try:
            if customer_form.is_valid() and address_form.is_valid():
                customer = customer_form.save(commit=False)
                customer.phone_number = request.user
                customer.save()
                address = address_form.save(commit=False)
                address.customer = customer
                address.save()
                messages.success(request, "اطلاعات شما با موفقیت ذخیره شد.")
                return redirect('checkout')
            else:
                # نمایش خطاهای فرم
                if not customer_form.is_valid():
                    for field, errors in customer_form.errors.items():
                        for error in errors:
                            messages.error(request, f"خطا در فیلد {field}: {error}")

                if not address_form.is_valid():
                    for field, errors in address_form.errors.items():
                        for error in errors:
                            messages.error(request, f"خطا در فیلد {field}: {error}")
        except Exception as e:
            messages.error(request, f"خطایی رخ داد: {str(e)}")
    else:
        customer_form = CustomerForm()
        address_form = AddressForm()

    return render(request, 'store/profile.html', {
        'customer_form': customer_form,
        'address_form': address_form
    })


def customer_address_update_view(request, pk):
    try:
        customer = get_object_or_404(Customer, pk=pk)
        address, created = Address.objects.get_or_create(customer=customer)

        if request.method == "POST":
            customer_form = CustomerForm(request.POST, instance=customer)
            address_form = AddressForm(request.POST, instance=address)

            if customer_form.is_valid() and address_form.is_valid():
                customer_form.save()
                address_form.save()
                messages.success(request, "اطلاعات شما با موفقیت به‌روزرسانی شد")
                return redirect('checkout')
            else:
                # نمایش خطاهای فرم
                for field, errors in customer_form.errors.items():
                    for error in errors:
                        messages.error(request, f"خطا در {customer_form[field].label}: {error}")

                for field, errors in address_form.errors.items():
                    for error in errors:
                        messages.error(request, f"خطا در {address_form[field].label}: {error}")
        else:
            customer_form = CustomerForm(instance=customer)
            address_form = AddressForm(instance=address)

    except Exception as e:
        messages.error(request, f"خطایی رخ داد: {str(e)}")
        return redirect('some_fallback_url')

    return render(request, 'store/edit_profile.html', {
        'customer_form': customer_form,
        'address_form': address_form
    })


def payment_process(request, pk):
    order = Order.objects.filter(
        pk=pk,
        status=Order.ORDER_STATUS_UNPAID
    ).first()
    if not order:
        messages.error(request, 'سفارش نامعتبر است.')
        return redirect('order_history')

    sep = SEPPayment(
        settings.SEP_TERMINAL_ID,
        settings.SEP_PASSWORD,
        settings.SEP_CALLBACK_URL
    )

    # فقط order را ارسال کنید
    res = sep.get_token(order)

    if not res.get('success'):
        err = res.get('error', 'خطای نامشخص')
        messages.error(request, f'خطا در ارتباط با درگاه: {err}')
        logger.error("SEP token request failed for order %s", order.id)
        return redirect('checkout')

    # توکن از داخل get_token در order.sep_token ذخیره شده است
    return render(request, 'store/payment_redirect.html', {
        'token': order.sep_token,
    })


@csrf_exempt
@require_POST
def payment_callback(request):
    """
    این view فقط POST درگاه را می‌گیرد،
    سفارش را وریفای می‌کند،
    و در نهایت redirect می‌کند به sep_result؟res_num=...
    هرگز session را دست نمی‌زند.
    """
    data = {**request.GET.dict(), **request.POST.dict()}
    res_num = data.get('ResNum')
    ref_num = data.get('RefNum')
    state = data.get('State')
    status_ = data.get('Status')

    # ۱) پیدا کردن سفارش
    try:
        order = Order.objects.get(pk=res_num)
    except Order.DoesNotExist:
        logger.warning("SEP callback: order not found %s", res_num)
        # بی‌خیال، باز هم redirect به صفحه نتیجه (ناموفق)
        return redirect(f"{reverse('sep_result')}?res_num={res_num}")

    # ۲) اگر قبلاً پردازش شده، نادیده بگیر
    if order.status != Order.ORDER_STATUS_UNPAID:
        logger.info("SEP callback ignored, already processed %s", order.id)
        return redirect(f"{reverse('sep_result')}?res_num={res_num}")

    # ۳) بررسی اولیه
    success_initial = (state and state.upper()=='OK') or (status_=='2')
    if not success_initial:
        order.status = Order.ORDER_STATUS_CANCELED
        order.sep_payment_data = {'callback': data}
        order.save(update_fields=['status','sep_payment_data'])
        return redirect(f"{reverse('sep_result')}?res_num={res_num}")

    # ۴) وریفای نهایی با SEP
    sep = SEPPayment(settings.SEP_TERMINAL_ID,
                     settings.SEP_PASSWORD,
                     settings.SEP_CALLBACK_URL)
    try:
        vr = sep.verify_payment(ref_num)
    except Exception as e:
        logger.error("SEP verification failed for order %s", order.id)
        order.status = Order.ORDER_STATUS_CANCELED
        order.sep_payment_data = {
            'verify_exception': str(e),
            'callback': data
        }
        order.save(update_fields=['status','sep_payment_data'])
        return redirect(f"{reverse('sep_result')}?res_num={res_num}")

    if not vr.get('success'):
        order.status = Order.ORDER_STATUS_CANCELED
        order.sep_payment_data = {
            'verify_error': vr.get('error'),
            'callback': data
        }
        order.save(update_fields=['status','sep_payment_data'])
        return redirect(f"{reverse('sep_result')}?res_num={res_num}")

    # ۵) نهایی‌سازی پرداخت
    try:
        with transaction.atomic():
            o = Order.objects.select_for_update().get(pk=order.pk)
            if not o.inventory_deducted:
                for item in OrderItem.objects.filter(order=o):
                    p = item.product
                    p.inventory = F('inventory') - item.quantity
                    p.save(update_fields=['inventory'])
                o.inventory_deducted = True

            o.status = Order.ORDER_STATUS_PAID
            o.sep_refnum = ref_num
            o.sep_payment_data = {
                'verify': vr.get('data'),
                'callback': data
            }
            o.save(update_fields=[
                'status','sep_refnum','sep_payment_data','inventory_deducted'
            ])
    except Exception:
        logger.exception("Error finalizing order %s", order.id)
        # باز هم redirect به نتیجهٔ ناموفق
        return redirect(f"{reverse('sep_result')}?res_num={res_num}")
        # ۸) ارسال پیامک موفقیت
    send_kavenegar(
        mobile=order.mobile,
        token=str(order.id),
        token2=str(ref_num),
        template="ordersuccessuser"
    )
    send_kavenegar(
        mobile=settings.KAVENEGAR_ADMIN_PHONE,
        token=str(order.id),
        template="ordersuccessadmin"
    )

    # ۷) اکنون کار تمام است: کاربر را به صفحه‌ی نتیجه هدایت می‌کنیم
    return redirect(f"{reverse('sep_result')}?res_num={res_num}")


def sep_result(request):
    """
    نمایش نتیجه به کاربر:
     - اگر unpaid: pending
     - اگر canceled: failed
     - اگر paid: success و پاک کردن items-only از cart
    """
    res_num = request.GET.get('res_num')
    order = get_object_or_404(Order, pk=res_num)

    if order.status == Order.ORDER_STATUS_UNPAID:
        return render(request, 'store/error.html', {
            'msg': 'در حال پردازش پرداخت، لطفاً چند لحظه صبر کنید.'
        })

    if order.status == Order.ORDER_STATUS_CANCELED:
        return render(request, 'store/failed.html', {
            'msg': 'پرداخت ناموفق بود.'
        })

    # پرداخت موفق: فقط آیتم‌های سبد را پاک کن
    try:
        cart = Cart.get_cart(request)
        cart.clear()
    except Exception as e:
        logger.error("Error clearing cart items-only: %s", e)

    return render(request, 'store/success.html', {
        'order': order,
        'ref_id': order.sep_refnum,
        'message': 'پرداخت با موفقیت انجام شد.'
    })


class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = 'store/order_detail.html'
    context_object_name = 'order'

    def get_queryset(self):
        return super().get_queryset().select_related('mobile').prefetch_related('items__product')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payment_method'] = "درگاه بانک صادرات"  # میتوانید از مدل واقعی پرداخت استفاده کنید
        return context


def update_shipping(request):
    shipping_type = request.POST.get('shipping_type', '')
    shipping_cost_map = {
        'tipax': 30000,
        'freight': 30000,
        'city': 0,
        'pickup': 0,
    }
    shipping_cost = shipping_cost_map.get(shipping_type, 0)

    # ذخیرهٔ هزینه و نوع ارسال در سشن
    request.session['shipping_cost'] = shipping_cost
    request.session['shipping_type'] = shipping_type
    request.session.setdefault('discount_amount', 0)
    request.session.setdefault('discount_code', '')
    cart = Cart.get_cart(request)
    total_before_discount = cart.get_total_price + shipping_cost
    discount_amount = request.session.get('discount_amount', 0)

    if request.session.get('discount_code'):
        try:
            discount = Discount.objects.get(
                code=request.session['discount_code'],
                start_time__lte=timezone.now(),
                end_time__gte=timezone.now()
            )
            discounted_price = discount.get_discount(total_before_discount)
            discount_amount = total_before_discount - discounted_price
            request.session['discount_amount'] = discount_amount
            total_amount = discounted_price
        except Discount.DoesNotExist:
            request.session.pop('discount_code', None)
            request.session.pop('discount_amount', None)
            total_amount = total_before_discount
    else:
        total_amount = total_before_discount - discount_amount

    return JsonResponse({
        'shipping_cost': shipping_cost,
        'total_amount': total_amount
    })


class OrderHistoryView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'store/order_history.html'
    context_object_name = 'orders'

    def get_queryset(self):
        # Filter orders for the currently logged-in user
        return Order.objects.filter(mobile=self.request.user).order_by('-datetime_created')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add additional context data if needed
        context['total_orders'] = self.object_list.count()
        context['paid_orders'] = self.object_list.filter(status=Order.ORDER_STATUS_PAID).count()
        context['unpaid_orders'] = self.object_list.filter(status=Order.ORDER_STATUS_UNPAID).count()
        context['canceled_orders'] = self.object_list.filter(status=Order.ORDER_STATUS_CANCELED).count()

        return context


def order_invoice_pdf(request, order_id):
    # دریافت سفارش
    order = get_object_or_404(Order, id=order_id)
    order.jalali_datetime_created = datetime2jalali(order.datetime_created) \
        .strftime('%Y/%m/%d %H:%M')

    # رندر HTML
    template = get_template('store/invoice.html')
    html_string = template.render({'order': order})

    # تولید PDF
    # base_url برای resolve کردن URL های استاتیک لازم است
    pdf_file = HTML(
        string=html_string,
        base_url=request.build_absolute_uri('/')  # ریشهٔ پروژه
    ).write_pdf()

    # بازگشت پاسخ PDF
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="invoice_order_{order.id}.pdf"'
    return response


@require_POST
def apply_discount(request):
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'برای استفاده از تخفیف باید وارد حساب کاربری خود شوید'
        })
        # بررسی وجود پروفایل کاربر
    if not Customer.objects.filter(phone_number=request.user).exists():
        return JsonResponse({
            'success': False,
            'message': 'برای استفاده از کد تخفیف باید پروفایل خود را تکمیل کنید.',
            'redirect_url': reverse('profile')
        })

    discount_code = request.POST.get('discount_code', '').strip()
    current_time = timezone.now()

    try:
        # بررسی کد تخفیف
        discount = Discount.objects.get(
            code=discount_code,
            start_time__lte=current_time,
            end_time__gte=current_time
        )

        # بررسی اینکه آیا کاربر قبلاً از این کد تخفیف استفاده کرده یا نه
        if DiscountUsage.objects.filter(user=request.user, discount=discount).exists():
            return JsonResponse({
                'success': False,
                'message': 'شما قبلاً از این کد تخفیف استفاده کرده‌اید.'
            })

        # تلاش برای پیدا کردن سفارش مربوطه
        order = get_or_create_order_for_user(request.user, request)
        if not order:
            return JsonResponse({
                'success': False,
                'message': 'هیچ سفارشی برای این کاربر پیدا نشد.'
            })

        # ثبت استفاده از کد تخفیف برای کاربر
        DiscountUsage.objects.create(user=request.user, discount=discount, order_id=order.id)

        # ذخیره کد تخفیف در سشن
        request.session['discount_code'] = discount_code

    except Discount.DoesNotExist:
        request.session.pop('discount_code', None)
        request.session.pop('discount_amount', None)  # حذف مقدار تخفیف در صورت وجود خطا
        return JsonResponse({
            'success': False,
            'message': 'کد تخفیف معتبر نیست یا منقضی شده است'
        })

    # محاسبه مبلغ قبل و بعد از تخفیف
    cart = Cart.get_cart(request)
    shipping_cost = request.session.get('shipping_cost', 0)  # مقدار پیش‌فرض 0

    total_before_discount = cart.get_total_price + shipping_cost
    discounted_price = discount.get_discount(total_before_discount)
    discount_amount = total_before_discount - discounted_price
    request.session['discount_amount'] = discount_amount
    request.session['total_after_discount'] = discounted_price

    return JsonResponse({
        'success': True,
        'discount_amount': discount_amount,
        'total_amount': discounted_price,
        'message': f'تخفیف {discount.name} با موفقیت اعمال شد'
    })


class TermsConditionView(TemplateView):
    template_name = 'Rules_and_regulations.html'
