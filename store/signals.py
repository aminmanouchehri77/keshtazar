from .cart import SessionCart
from .models import Cart, OrderItem
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import pre_save, post_delete


@receiver(user_logged_in)
def sync_session_with_db(sender, request, user, **kwargs):
    cart = SessionCart(request)

    for item in cart:
        Cart.objects.get_or_create(
            user_id=user.id,
            product_id=item['product_id'],
            defaults={
                'quantity': item['quantity']
            }
        )


# @receiver(pre_save, sender=OrderItem)
# def update_stock_on_save(sender, instance, **kwargs):
#     if instance.pk:  # بررسی اگر سفارش در حال ویرایش است
#         old_instance = OrderItem.objects.get(pk=instance.pk)
#         difference = instance.quantity - old_instance.quantity
#     else:
#         difference = instance.quantity
#
#     if instance.product.inventory >= difference:
#         instance.product.inventory -= difference
#         instance.product.save()
#     else:
#         raise ValueError("موجودی محصول کافی نیست")
#
#
# @receiver(post_delete, sender=OrderItem)
# def restore_stock_on_delete(sender, instance, **kwargs):
#     instance.product.inventory += instance.quantity
#     instance.product.save()
