
from django.urls import path, include, register_converter
from .converters import PersianSlugConverter
from . import views
from .views import payment_process, payment_callback, OrderDetailView, update_shipping, apply_discount, \
    OrderHistoryView, TermsConditionView, order_invoice_pdf

register_converter(PersianSlugConverter, 'pslug')
urlpatterns = [
    path('shop/', views.store_products_list_view, name='product_list'),
    path('product-detail/<int:pk>/<pslug:slug>/', views.products_details_view, name='product_detail'),
    path('faq/', views.faq_view, name='faq'),
    path('searched-products/', views.products_search_view, name='searched_product_list'),
    path('add-to-cart/', views.add_to_cart, name="add_to_cart"),
    path('cart/', views.cart_detail_view, name="cart_detail"),
    path('cart/remove/<int:product_id>/', views.remove_from_cart, name="remove_from_cart"),
    path('checkout/', views.checkout_view, name="checkout"),
    path('profile/', views.profile_view, name="profile"),
    path('edit-profile/<int:pk>', views.customer_address_update_view, name="edit_profile"),
    path('process/<int:pk>', payment_process, name='payment_process'),
    path('callback/', payment_callback, name='payment_callback'),
    path('sep-result/', views.sep_result, name='sep_result'),
    path('orders/<int:pk>/', OrderDetailView.as_view(), name='order_detail'),
    path('update-shipping/', update_shipping, name='update_shipping'),
    path('apply-discount/', apply_discount, name='apply_discount'),
    path('order-history/', OrderHistoryView.as_view(), name='order_history'),
    path('terms-condition/', TermsConditionView.as_view(), name='terms_condition'),
    path('order/<int:order_id>/invoice/', order_invoice_pdf, name='order_invoice_pdf'),
]
