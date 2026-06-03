from django.db.models import Avg, FloatField
from django.db.models.functions import Cast
from store.models import Product, Comment
from .cart import Cart
from .models import Product


def cart_context(request):
    cart_object = Cart.get_cart(request)
    if cart_object:
        if not request.user.is_authenticated:
            product_ids = cart_object.product_ids
            products = Product.objects.filter(id__in=product_ids)
            for product in products:
                cart_object[str(product.id)]['product'] = product

        all_total_price = 0
        cart_len = 0
        for item in cart_object:
            item['total_price'] = int(item['price']) * int(item['quantity'])
            all_total_price += item['total_price']
            cart_len += item['quantity']
        cart_object.all_total_price = all_total_price
        cart_object.cart_len = cart_len
    return {'cart': cart_object}


def product_ratings(request):
    """محاسبه میانگین امتیاز تمامی محصولات"""
    products = Product.objects.all()
    ratings = {}

    for product in products:
        comments = product.comments.filter(
            status=Comment.COMMENT_STATUS_APPROVED
        )
        if comments.exists():
            avg_result = comments.annotate(
                numeric_star=Cast('star', FloatField())
            ).aggregate(average=Avg('numeric_star'))
            average_rating = round(avg_result['average'], 1) if avg_result['average'] else 0
        else:
            average_rating = 0
        ratings[product.id] = average_rating

    return {
        'product_ratings': ratings
    }