from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from store.models import Product, Comment, Order, OrderItem, Discount, Customer, DiscountUsage
from store.views import products_details_view
from unittest.mock import patch
from django.test import TestCase

User = get_user_model()


class ProductDetailViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create(mobile='09123456789')
        self.product = Product.objects.create(
            name='Test Product',
            inventory=10,
            unit_price=100000
        )

    def test_comment_submission_without_purchase(self):
        request = self.factory.post('/products/1/')
        request.user = self.user
        response = products_details_view(request, pk=self.product.id)

        self.assertContains(response, 'باید خریداری کرده باشید')
        self.assertEqual(Comment.objects.count(), 0)

    def test_successful_comment_submission(self):
        # ایجاد سفارش پرداخت شده
        order = Order.objects.create(
            mobile=self.user,
            status=Order.ORDER_STATUS_PAID
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=1,
            price=self.product.unit_price
        )

        data = {
            'body': 'Great product!',
            'star': '5'
        }
        request = self.factory.post('/products/1/', data)
        request.user = self.user
        response = products_details_view(request, pk=self.product.id)

        self.assertEqual(Comment.objects.count(), 1)
        self.assertEqual(response.status_code, 200)


class PaymentCallbackTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            total_price=100000,
            zarinpal_authority='test_authority'
        )

    @patch('requests.post')
    def test_successful_payment(self, mock_post):
        mock_response = {
            'data': {
                'code': 100,
                'ref_id': '123456',
                'errors': []
            }
        }
        mock_post.return_value.json.return_value = mock_response

        response = self.client.get(
            '/payment/callback/',
            {'Authority': 'test_authority', 'Status': 'OK'}
        )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'p')
        self.assertEqual(self.order.zarinpal_ref_id, '123456')
        self.assertTemplateUsed(response, 'store/success.html')

    @patch('requests.post')
    def test_expired_discount_code(self, mock_post):
        mock_response = {
            'errors': {
                'code': -51,
                'message': 'کد تخفیف منقضی شده'
            }
        }
        mock_post.return_value.json.return_value = mock_response

        response = self.client.get(
            '/payment/callback/',
            {'Authority': 'test_authority', 'Status': 'OK'}
        )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'c')
        self.assertTemplateUsed(response, 'store/failed.html')


class CartFunctionalityTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Test Product',
            inventory=5,
            unit_price=50000
        )

    def test_add_to_cart(self):
        response = self.client.post(
            '/cart/add/',
            {'product_id': self.product.id, 'quantity': 2, 'update1': '0'}
        )

        cart = self.client.session.get('cart')
        self.assertEqual(cart[str(self.product.id)]['quantity'], 2)
        self.assertRedirects(response, '/cart/')

    def test_remove_from_cart(self):
        session = self.client.session
        session['cart'] = {str(self.product.id): {'quantity': 1}}
        session.save()

        response = self.client.get(f'/cart/remove/{self.product.id}/')
        self.assertNotIn(str(self.product.id), self.client.session['cart'])


class DiscountTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(
            mobile='09123456789',
            password='testpass123'
        )
        self.customer = Customer.objects.create(
            phone_number=self.user,
            first_name='John'
        )
        self.discount = Discount.objects.create(
            code='SUMMER20',
            value=20,
            max_usage=3
        )

    def test_valid_discount_application(self):
        self.client.force_login(self.user)
        response = self.client.post(
            '/apply-discount/',
            {'discount_code': 'SUMMER20'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertJSONEqual(
            response.content,
            {'success': True, 'message': 'تخفیف SUMMER20 با موفقیت اعمال شد'}
        )
        self.assertEqual(self.discount.usage_count, 1)

    def test_reusing_discount_code(self):
        DiscountUsage.objects.create(
            user=self.user,
            discount=self.discount,
            order_id=1
        )

        self.client.force_login(self.user)
        response = self.client.post(
            '/apply-discount/',
            {'discount_code': 'SUMMER20'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertJSONEqual(
            response.content,
            {'success': False, 'message': 'شما قبلاً از این کد تخفیف استفاده کرده‌اید.'}
        )


class OrderIntegrationTests(TestCase):
    def test_full_order_workflow(self):
        # ساخت محصولات
        product1 = Product.objects.create(name='Product 1', unit_price=100000, inventory=5)
        product2 = Product.objects.create(name='Product 2', unit_price=200000, inventory=3)

        # افزودن به سبد خرید
        self.client.post('/cart/add/', {'product_id': product1.id, 'quantity': 2})
        self.client.post('/cart/add/', {'product_id': product2.id, 'quantity': 1})

        # بررسی سبد خرید
        cart_response = self.client.get('/cart/')
        self.assertContains(cart_response, 'Product 1')
        self.assertContains(cart_response, '300,000 تومان')  # (100,000 * 2) + 200,000

        # انجام سفارش
        checkout_response = self.client.post('/checkout/')
        order = Order.objects.first()
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.total_price, 300000)
