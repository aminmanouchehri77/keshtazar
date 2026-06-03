# orders/templatetags/shipping_extras.py
from django import template
import re

register = template.Library()


@register.filter
def strip_parentheses(value):
    """
    همه چیز از اولین '(' تا انتهای رشته را حذف می‌کند
    و فقط قسمت قبل از '(' را برمی‌گرداند.
    اگر ورودی str نباشد یا '(' در آن نباشد،
    همان value را برمی‌گرداند.
    """
    if not isinstance(value, str):
        return value
    # با این الگو هر چیزی از اولین '(' تا انتها را حذف می‌کنیم
    return re.sub(r'\s*\(.*$', '', value).strip()
