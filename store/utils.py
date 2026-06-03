
from django.conf import settings
from django.db import transaction
from requests import RequestException
from store.models import OrderItem, Order, Discount
from .cart import Cart
import logging
from decimal import Decimal
import requests
import os
from django.contrib.staticfiles import finders

logger = logging.getLogger(__name__)


def save_order(cart, request, shipping_type):
    shipping_cost = request.session.get('shipping_cost', 0)
    discount_amount = request.session.get('discount_amount', 0)
    order = Order.objects.create(
        mobile=request.user,
        total_price=(cart.get_total_price + shipping_cost) - discount_amount,
        first_name=request.user.customer.first_name,
        last_name=request.user.customer.last_name,
        address=request.user.customer.address,
        province=request.user.customer.address.province,
        city=request.user.customer.address.city,
        postal_code=request.user.customer.address.postal_code,
        note=request.POST.get('notes'),
        shipping_type=shipping_type,
    )

    for item in cart:
        OrderItem.objects.create(
            order=order,
            product_id=item['product_id'],
            quantity=item['quantity'],
            unit_price=item['price']
        )
    return order


def get_discount(request, cart):
    discount_code = request.POST.get('discount_code')
    order_price = cart.get_total_price

    result = {
        'total_price': order_price,
        'discount_code': discount_code,
        'discount_id': None,
        'total_discount': 0
    }

    if not discount_code:
        return result

    try:
        discount = Discount.objects.active().get(code=discount_code)
        result['discount_id'] = discount.id
        result['total_price'] = new_price = discount.get_discount(order_price)
        result['total_discount'] = order_price - new_price
    except Discount.DoesNotExist:
        pass

    return result


def get_or_create_order_for_user(user, request):
    # تلاش برای بدست آوردن سفارش فعلی کاربر
    order = Order.objects.filter(mobile=user, status=Order.ORDER_STATUS_UNPAID).first()
    if not order:
        # اگر سفارش وجود ندارد، ایجاد یک سفارش جدید
        order = save_order(Cart.get_cart(request), request)
    return order


class SEPPayment:
    """
    کلاس مدیریت ارتباط با درگاه اینترنتی SEP (Minimal v3.3).
    فقط پارامترهای الزامی برای توکن و Verify ارسال می‌شود.
    """

    def __init__(self, terminal_id, password, callback_url, timeout=30):
        """
        :param terminal_id: شناسه ترمینال (MID)
        :param password:     رمز ترمینال (برای نگهداری، در توکن استفاده نمی‌شود)
        :param callback_url: آدرس بازگشت پس از پرداخت (باید دقیقاً با پنل SEP مطابقت داشته باشد)
        :param timeout:      زمان تایم‌اوت درخواست‌ها (ثانیه)
        """
        self.terminal_id = terminal_id
        self.password = password
        self.callback_url = callback_url
        self.timeout = timeout

        # آدرس‌های سرویس مطابق مستند Minimal v3.3
        self.token_url = "https://sep.shaparak.ir/onlinepg/onlinepg"
        self.verify_url = "https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/VerifyTranscation"

    def get_token(self, order):
        """
        درخواست توکن از SEP با پارامترهای Minimal v3.3.

        :param order: شیء Order (باید فیلد total_price و id ست شده باشد)
        :return: دیکشنری با کلیدهای:
                 - success: bool
                 - token:   str (در صورت موفق)
                 - error:   str (در صورت خطا)
                 - data:    dict (پاسخ خام JSON)
        """
        try:
            # تبدیل مبلغ به عدد صحیح
            amount_int = int(Decimal(order.total_price))*10

            # استخراج شماره همراه از order.mobile (فیلد User.mobile یا User.phone_number)
            cell = ""
            if hasattr(order.mobile, 'mobile'):
                cell = order.mobile.mobile or ""
            elif hasattr(order.mobile, 'phone_number'):
                cell = order.mobile.phone_number or ""

            # ساخت payload فقط با فیلدهای الزامی
            payload = {
                "action": "token",
                "TerminalId": self.terminal_id,
                "Amount": amount_int,
                "ResNum": str(order.id),
                "RedirectUrl": self.callback_url,
                "CellNumber": cell,
            }
            logger.info("SEP Token Payload: %s", payload)

            # ارسال POST JSON
            resp = requests.post(
                self.token_url,
                json=payload,
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )
            data = resp.json() if resp.ok else {}
            logger.info("SEP Token Response: %s", data)

            # بررسی موفقیت
            if resp.ok and data.get("status") == 1:
                token = data["token"]
                # ذخیره توکن در سفارش
                with transaction.atomic():
                    order.sep_token = token
                    order.save(update_fields=["sep_token"])
                    print(token)
                return {"success": True, "token": token, "data": data}

            # خطای منطقی
            return {
                "success": False,
                "status_code": resp.status_code,
                "error": f"{data.get('errorCode', '?')} - {data.get('errorDesc', '?')}",
                "data": data
            }

        except Exception as e:
            logger.exception("Exception in SEPPayment.get_token")
            return {"success": False, "error": str(e)}

    def verify_payment(self, ref_num):
        payload = {
            "RefNum": ref_num,
            "TerminalNumber": self.terminal_id,  # کلید باید TerminalNumber باشد
        }
        headers = {
            "Content-Type": "application/json",  # به جای form باید json باشد
            "Accept": "application/json"
        }
        logger.info("SEP Verify -> URL: %s, payload: %s", self.verify_url, payload)

        try:
            resp = requests.post(
                self.verify_url,
                json=payload,  # ارسال دیتا به صورت بدنه json
                headers=headers,
                timeout=self.timeout
            )
        except RequestException as e:
            logger.error("Network error in verify: %s", e)
            return {"success": False, "error": f"Network error: {e}"}

        logger.info("SEP Verify response | status=%s | content-type=%s | text[0:200]=%s",
                    resp.status_code,
                    resp.headers.get("Content-Type"),
                    resp.text.strip()[:200])

        ct = resp.headers.get("Content-Type", "")
        text = resp.text.strip()

        # اگر JSON برگشت داد:
        if resp.ok and ct.startswith("application/json"):
            try:
                data = resp.json()
                # بررسی حالت موفقیت (طبق مستند/پاسخ واقعی)
                if data.get("status") in (1, "1") or data.get("ResultCode") in (0, "0", 1, "1", "OK"):
                    return {"success": True, "data": data}
                return {
                    "success": False,
                    "status_code": resp.status_code,
                    "error": data.get("Message") or data.get("ErrorDescription") or str(data),
                    "data": data
                }
            except Exception as e:
                logger.error("JSON parse error: %s", e)
                return {"success": False, "error": f"JSON parse error: {e}", "raw_resp": text}

        # در غیر این صورت:
        return {
            "success": False,
            "status_code": resp.status_code,
            "error": "invalid response",
            "raw_resp": text
        }


def send_kavenegar(
        mobile: str,
        token: str,
        template: str,
        receptor: str = None,
        token2: str = None,
        token3: str = None,
) -> dict:
    """
    ارسال پیامک با Kavenegar از طریق endpoint verify/lookup.json

    Args:
        mobile: شماره موبایل گیرنده.
        token: مقدار متغیر (OTP یا هر داده دیگری).
        template: نام قالب در پنل کاوه‌نگار.
        receptor: اگر می‌خواهید چند گیرنده با کاما جدا کنید، می‌توانید این پارامتر را استفاده کنید.
        token2: مقدار دوم برای قالب‌هایی که پارامتر دوم دارند.
        token3: مقدار سوم برای قالب‌هایی که پارامتر سوم دارند.
    Returns:
        دیکشنری پاسخ از API در صورت موفق، یا {} در صورت خطا.
    """
    apikey = settings.KAVENEGAR_API_KEY
    url = f'https://api.kavenegar.com/v1/{apikey}/verify/lookup.json'
    params = {
        'receptor': receptor or mobile,
        'token': token,
        'template': template,
    }
    if token2:
        params['token2'] = token2
    if token3:
        params['token3'] = token3
    try:
        resp = requests.post(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Kavenegar SMS sent to %s, template=%s, resp=%s", mobile, template, data)
        return data
    except requests.RequestException as e:
        logger.error("Kavenegar HTTP error sending to %s: %s", mobile, e)
    except ValueError as e:
        logger.error("Invalid JSON from Kavenegar for %s: %s", mobile, e)
    except Exception as e:
        logger.exception("Unexpected error sending SMS to %s:", mobile)
    return {}


