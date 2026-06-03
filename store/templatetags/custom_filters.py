from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter(name='comma_separator')
def comma_separator(value):
    """
    افزودن کاما به اعداد به ازای هر سه رقم
    مثال: 1000000 -> 1,000,000
    """
    try:
        # تبدیل ورودی به عدد صحیح
        value = int(value)
        # فرمت کردن عدد با کاما
        return "{:,}".format(value)
    except (ValueError, TypeError):
        # در صورت خطا، مقدار اصلی برگردانده می‌شود
        return value
