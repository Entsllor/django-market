from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.test import TestCase
from django.urls import reverse_lazy

from currencies.services import DEFAULT_CURRENCY_CODE, exchange_to
from .base_case import BaseMarketTestCase, assert_difference, TestBaseWithFilledCatalogue, FailedToCreateObject
from ..models import Market, Product, ProductCategory, Operation, ProductType, Order, OrderItem, OrderStatusChoices, \
    User
from ..services import top_up_balance, make_purchase, prepare_order
from ..views import ProductCreateView, ProductEditView, CatalogueView, MarketEditView, MarketCreateView, \
    CartView, CheckOutView, TopUpView, OperationHistoryView, OrderDetail, ProductTypeEdit, UserMarketView, ShippingPage, \
    PayingView


def prepare_product_data_to_post(data) -> dict:
    data = data.copy()
    market = data.get('market')
    category = data.get('category')
    if market and isinstance(market, Market):
        data['market'] = market.id
    if category and isinstance(category, ProductCategory):
        data['category'] = category.id
    return data


class ViewTestMixin(TestCase):
    ViewClass = None
    page_url = None

    def post_to_page(self, url=None, data=None, **kwargs):
        if url is None:
            url = self.get_url()
        return self.client.post(path=url, data=data, **kwargs)

    def get_from_page(self, url=None, **kwargs):
        if url is None:
            url = self.get_url()
        return self.client.get(path=url, **kwargs)

    def assertRedirectsAuth(self, response):
        self.assertRedirects(response, reverse_lazy('accounts:log_in') + '?next=' + self.get_url())

    def checkUsedTemplate(self, response):
        self.assertTemplateUsed(response, self.ViewClass.template_name)

    def _test_redirect_if_not_logged_in(self):
        self.client.logout()
        response = self.get_from_page()
        self.assertRedirectsAuth(response)

    def _test_correct_template(self):
        response = self.get_from_page()
        self.checkUsedTemplate(response)

    def get_url(self):
        return self.page_url


class CatalogueTest(ViewTestMixin):
    ViewClass = CatalogueView
    page_url = reverse_lazy('market_app:catalogue')

    def test_correct_template(self):
        self._test_correct_template()


class ProductCreateTest(ViewTestMixin, BaseMarketTestCase):
    ViewClass = ProductCreateView
    page_url = reverse_lazy('market_app:create_product')

    def setUp(self) -> None:
        self.create_currencies()
        super(ProductCreateTest, self).setUp()
        self.market = self.seller.market
        self.product_data = {
            'name': 'TestProductName', 'description': 'text', 'market': self.market,
            'original_price': 100, 'discount_percent': 0,
            'available': True, 'category': self.category
        }

    def post_to_product_create(
            self, data: dict = None, extra_data: dict = None,
            check_unique=True, currency_code=DEFAULT_CURRENCY_CODE, **kwargs):
        if data is None:
            data = self.product_data
        data = data.copy()
        if extra_data:
            data.update(extra_data)
        data = prepare_product_data_to_post(data)
        if check_unique:
            self.assertObjectDoesNotExist(Product.objects, name=data['name'])
        response = self.post_to_page(self.page_url, data=data | {'currency_code': currency_code}, **kwargs)
        try:
            self.try_to_set_created_product(name=data['name'])
        except ObjectDoesNotExist:
            raise FailedToCreateObject("Failed to create the product. Make sure the data is valid.")
        return response

    def try_to_set_created_product(self, **data):
        self.created_product = Product.objects.get(**data)

    def test_can_create_product(self):
        self.log_in_as_seller()
        self.post_to_product_create()
        for key in self.product_data:
            self.assertEqual(getattr(self.created_product, key), self.product_data[key])

    def test_create_in_default_currency(self):
        self.log_in_as_seller()
        expected_price = exchange_to(DEFAULT_CURRENCY_CODE, 1000)
        self.assertNotEqual(expected_price, self.product_data['original_price'])
        self.post_to_product_create(extra_data={'original_price': 1000}, currency_code=DEFAULT_CURRENCY_CODE)
        real_price = self.created_product.original_price
        self.assertEqual(expected_price, real_price)

    def test_create_in_another_currency(self):
        self.log_in_as_seller()
        expected_price = exchange_to(DEFAULT_CURRENCY_CODE, 1000, _from='RUB')
        self.assertNotEqual(expected_price, self.product_data['original_price'])
        self.post_to_product_create(extra_data={'original_price': 1000}, currency_code='RUB')
        real_price = self.created_product.original_price
        self.assertEqual(expected_price, real_price)

    def test_redirect_if_not_logged_in(self):
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_customer()
        self._test_correct_template()


class ProductEditTest(ViewTestMixin, BaseMarketTestCase):
    ViewClass = ProductEditView

    def get_url(self):
        return reverse_lazy('market_app:edit_product', kwargs={'pk': self.product.pk})

    def setUp(self) -> None:
        self.create_currencies()
        super(ProductEditTest, self).setUp()
        self.new_category = self.create_category()
        self.old_data = {
            'name': 'OldProductName', 'description': 'text',
            'original_price': 100, 'discount_percent': 0,
            'available': True, 'category': self.category
        }
        self._product = self.create_product(**self.old_data)
        self.new_data = {
            'name': 'NewProductName', 'description': 'NewText',
            'original_price': 50, 'discount_percent': 50, 'category': self.new_category
        }

    @property
    def product(self):
        return Product.objects.get(pk=self._product.pk)

    def post_to_product_edit(self, product_id: int, data_to_update: dict,
                             currency_code: str = DEFAULT_CURRENCY_CODE, **kwargs):
        data_to_post = prepare_product_data_to_post(self.old_data.copy() | data_to_update)
        data_to_post.update({'currency_code': currency_code})
        return self.post_to_page(
            reverse_lazy('market_app:edit_product', args=[product_id]),
            data=data_to_post, **kwargs)

    def test_can_edit_product(self):
        self.log_in_as_seller()
        self.assertEqual(self.product.name, self.old_data['name'])
        self.post_to_product_edit(self.product.id, self.new_data)
        for key in self.new_data:
            self.assertEqual(getattr(self.product, key), self.new_data[key])

    def test_edit_product_if_user_is_not_owner(self):
        new_seller = self.create_seller(username='NewSeller')
        self.client.login(username=new_seller.username, password=self.password)
        self.assertEqual(self.product.name, self.old_data['name'])
        response = self.post_to_product_edit(self.product.id, self.new_data)
        self.assertEqual(response.status_code, 403)
        for key in self.new_data:
            self.assertEqual(getattr(self.product, key), self.old_data[key])

    def test_can_customer_edit_product(self):
        self.log_in_as_customer()
        self.assertEqual(self.product.name, self.old_data['name'])
        response = self.post_to_product_edit(self.product.id, self.new_data)
        self.assertEqual(response.status_code, 403)
        for key in self.new_data:
            self.assertEqual(getattr(self.product, key), self.old_data[key])

    def test_edit_price_in_default_currency(self):
        expected_price = exchange_to(DEFAULT_CURRENCY_CODE, 1000)
        self.assertNotEqual(expected_price, self.product.original_price)
        self.log_in_as_seller()
        self.post_to_product_edit(self.product.id, data_to_update={'original_price': 1000},
                                  currency_code=DEFAULT_CURRENCY_CODE)
        new_price = self.product.original_price
        self.assertEqual(new_price, expected_price)

    def test_edit_price_in_another_currency(self):
        expected_price = exchange_to(DEFAULT_CURRENCY_CODE, 100, _from='RUB')
        self.assertNotEqual(expected_price, self.product.original_price)
        self.log_in_as_seller()
        self.post_to_product_edit(self.product.id, data_to_update={'original_price': 100}, currency_code='RUB')
        new_price = self.product.original_price
        self.assertEqual(new_price, expected_price)

    def test_redirect_if_not_logged_in(self):
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_seller()
        self._test_correct_template()


class MarketEditTest(ViewTestMixin, BaseMarketTestCase):
    ViewClass = MarketEditView

    def setUp(self) -> None:
        super(MarketEditTest, self).setUp()
        self.old_data = {'name': 'OldName', 'description': 'OldDescription'}
        self.new_data = {'name': 'NewName', 'description': 'NewDescription'}
        self.market = self.seller.market
        for key, value in self.old_data.items():
            setattr(self.market, key, value)
        self.market.save()

    def get_url(self):
        return reverse_lazy('market_app:edit_market', kwargs={'pk': self.market.pk})

    def post_to_market_edit(self, market: Market, data_to_update: dict = None, **kwargs):
        if data_to_update is None:
            data_to_update = self.new_data
        response = self.post_to_page(
            reverse_lazy('market_app:edit_market', args=[market.id]),
            data=self.old_data.copy() | data_to_update, **kwargs
        )
        market.refresh_from_db()
        return response

    def test_can_edit_market_as_owner(self):
        self.log_in_as_seller()
        self.post_to_market_edit(market=self.market)
        for key in self.new_data:
            self.assertEqual(getattr(self.market, key), self.new_data[key])

    def test_edit_market_as_customer(self):
        self.log_in_as_customer()
        response = self.post_to_market_edit(market=self.market)
        for key in self.new_data:
            self.assertNotEqual(getattr(self.market, key), self.new_data[key])
        self.assertEqual(response.status_code, 403)

    def test_can_seller_edit_side_market(self):
        self.log_in_as_seller()
        another_seller = self.create_seller(username="AnotherSeller")
        another_market = self.create_market(owner=another_seller)
        response = self.post_to_market_edit(market=another_market)
        for key in self.new_data:
            self.assertNotEqual(getattr(self.market, key), self.new_data[key])
        self.assertEqual(response.status_code, 403)

    def test_can_another_seller_edit_side_market(self):
        another_seller = self.create_seller(username="AnotherSeller")
        self.client.login(username=another_seller, password=self.password)
        response = self.post_to_market_edit(market=self.market)
        for key in self.new_data:
            self.assertNotEqual(getattr(self.market, key), self.new_data[key])
        self.assertEqual(response.status_code, 403)

    def test_redirect_if_not_logged_in(self):
        self.log_in_as_seller()
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_seller()
        self._test_correct_template()


class MarketCreateViewsTest(ViewTestMixin, BaseMarketTestCase):
    ViewClass = MarketCreateView
    page_url = reverse_lazy('market_app:create_market')

    def setUp(self) -> None:
        self.market_data = {'name': 'TestMarketName', 'description': 'some text'}
        self.customer = self.create_customer()
        self.seller = self.create_seller()

    def post_to_market_create(self, data: dict = None, extra_data: dict = None, check_unique=True, **kwargs):
        if data is None:
            data = self.market_data
        data = data.copy()
        if extra_data:
            data.update(extra_data)

        if check_unique:
            self.assertObjectDoesNotExist(Market.objects, name=data['name'])
        response = self.post_to_page(self.page_url, data=data, **kwargs)
        self.try_set_created_market(**data)
        return response

    def try_set_created_market(self, **data):
        try:
            self.created_market: Market = Market.objects.get(**data)
        except ObjectDoesNotExist:
            self.created_market = None

    def test_can_create_market(self):
        self.log_in_as_seller()
        self.post_to_market_create()
        self.assertIsInstance(self.created_market, Market)
        self.assertEqual(self.created_market.owner.id, self.user.id)

    def test_redirects_after_create(self):
        self.log_in_as_seller()
        response = self.post_to_market_create()
        self.assertRedirects(response, MarketCreateView.success_url)

    def test_one_user_cannot_create_two_markets(self):
        self.log_in_as_seller()
        self.post_to_market_create()
        response = self.post_to_market_create(check_unique=False)
        self.assertEqual(response.status_code, 403)

    def test_redirects_if_user_already_have_market(self):
        self.log_in_as_seller()
        self.post_to_market_create()
        response = self.get_from_page()
        self.assertRedirects(response, reverse_lazy('market_app:user_market'), target_status_code=200)

    def test_redirect_if_not_logged_in(self):
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_customer()
        self._test_correct_template()


class ProductTypeEditTest(ViewTestMixin, BaseMarketTestCase):
    ViewClass = ProductTypeEdit

    def setUp(self) -> None:
        super(ProductTypeEditTest, self).setUp()
        self._product = self.create_product()
        self._product_type = self._product.create_product_type(units_count=0)

    def get_url(self):
        return reverse_lazy('market_app:edit_type', kwargs={'pk': self.product_type.pk})

    @property
    def product(self) -> Product:
        return Product.objects.get(pk=self._product.pk)

    @property
    def product_type(self):
        return ProductType.objects.get(pk=self._product_type.pk)

    def post_to_edit_type(self, pk, **kwargs):
        return self.post_to_page(
            reverse_lazy('market_app:edit_type', kwargs={'pk': pk}),
            data=kwargs
        )

    def check_data_to_compare(self):
        return self.product_type.units_count

    @assert_difference(10)
    def test_edit_if_owner(self):
        units_count = 10
        self.log_in_as_seller()
        self.post_to_edit_type(pk=self.product.pk, units_count=units_count)

    @assert_difference(0)
    def test_edit_if_not_owner(self):
        units_count = 10
        new_seller = self.create_seller(username='NewSeller')
        self.client.login(username=new_seller.username, password=self.password)
        response = self.post_to_edit_type(pk=self.product.pk, units_count=units_count)
        self.assertEqual(response.status_code, 403)

    @assert_difference(0)
    def test_edit_if_customer(self):
        units_count = 10
        self.log_in_as_customer()
        response = self.post_to_edit_type(pk=self.product.pk, units_count=units_count)
        self.assertEqual(response.status_code, 403)

    def test_redirect_if_not_logged_in(self):
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_seller()
        self._test_correct_template()


class CartViewTest(ViewTestMixin, TestBaseWithFilledCatalogue):
    ViewClass = CartView
    page_url = reverse_lazy('market_app:cart')
    success_url_name = 'market_app:checkout'

    def get_success_url(self, **kwargs):
        return reverse_lazy(self.success_url_name, kwargs=kwargs)

    def setUp(self) -> None:
        super(CartViewTest, self).setUp()
        self.log_in_as_customer()

    def test_can_change_order_at_cart_page(self):
        order_items = {'1': 5, '2': 3, '7': 5}
        self.fill_cart(order_items)
        changed_order_items = {'1': 8, '2': 0, '7': 2}
        self.post_to_page(data=changed_order_items)
        order: Order = self.user.orders.first()
        self.assertEqual(order.get_units_count_of('1'), 8)
        self.assertEqual(order.get_units_count_of('7'), 2)
        self.assertFalse(order.items.filter(product_type_id='2').exists())

    def test_redirect_if_form_is_valid(self):
        order_items = {'1': 5, '2': 3, '7': 5}
        response = self.post_to_page(data=order_items)
        order = self.user.orders.first()
        self.assertRedirects(response, self.get_success_url(pk=order.pk))

    def test_redirect_if_user_have_unpaid_order(self):
        self.post_to_page(data={'1': 5, '2': 3, '7': 5})
        first_order: Order = self.user.orders.first()
        response = self.post_to_page(data={'1': 2, '17': 1})
        self.assertRedirects(response, first_order.get_absolute_url())

    def test_redirect_if_not_logged_in(self):
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_customer()
        self._test_correct_template()


class CheckOutPageTest(ViewTestMixin, TestBaseWithFilledCatalogue):
    ViewClass = CheckOutView
    orders_list_url = reverse_lazy('market_app:orders')
    top_up_page_url = reverse_lazy('market_app:top_up')
    post_data = {
        'address': 'Some valid order address'
    }

    def setUp(self) -> None:
        super(CheckOutPageTest, self).setUp()
        self.log_in_as_customer()
        self.create_and_set_coupon(10, 100)
        self.create_and_set_coupon(20, 100)
        self.create_and_set_coupon(30, 100)
        self.prepare_order({'1': 5, '7': 5})

    def get_url(self):
        return reverse_lazy('market_app:checkout', kwargs={'pk': self.order.pk})

    def post_to_page(self, data: dict = None, extra_data: dict = None, **kwargs):
        if data is None:
            data = self.post_data
        if isinstance(extra_data, dict):
            data.update(extra_data)
        return super(CheckOutPageTest, self).post_to_page(data=data)

    def test_redirect_if_not_logged_in(self):
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self._test_correct_template()

    def test_can_change_activated_coupon(self):
        self.assertFalse(self.order.activated_coupon)
        self.post_to_page(extra_data={'activated_coupon': '1'})
        self.assertTrue(self.order.activated_coupon)


class TopUpViewTest(ViewTestMixin, TestBaseWithFilledCatalogue):
    ViewClass = TopUpView
    page_url = reverse_lazy('market_app:top_up')

    def setUp(self) -> None:
        self.create_currencies()
        super(TopUpViewTest, self).setUp()

    def test_redirect_if_not_logged_in(self):
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_customer()
        self._test_correct_template()

    @staticmethod
    def get_top_up_form_data(amount):
        return {
            'name_on_card': 'FULL NAME',
            'card_number': 9999999999999999,
            'top_up_amount': amount,
            'currency_code': DEFAULT_CURRENCY_CODE
        }

    def test_can_top_up_balance(self):
        self.log_in_as_customer()
        data = self.get_top_up_form_data(1000)
        self.assertEqual(self.user.balance.amount, 0)
        response = self.post_to_page(data=data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance.amount, 1000)
        self.assertRedirects(response, self.ViewClass.success_url)

    def test_redirect_to_unpaid_order_if_exists(self):
        self.log_in_as_customer()
        self.fill_cart({'1': 2, '7': 3})
        order = prepare_order(self.cart)
        top_up_form_data = self.get_top_up_form_data(1000)
        response = self.post_to_page(data=top_up_form_data)
        self.assertRedirects(response, reverse_lazy('market_app:checkout', kwargs={'pk': order.pk}))


class PayingTest(ViewTestMixin, TestBaseWithFilledCatalogue):
    ViewClass = PayingView
    post_data = {
        'name_on_card': 'SURNAME FIRSTNAME',
        'card_number': '9999_9999_9999_9999',
    }

    def setUp(self) -> None:
        super(PayingTest, self).setUp()
        self.unpaid_order = None
        self.log_in_as_customer()

    def get_url(self):
        return reverse_lazy('market_app:paying', kwargs={'pk': 1})

    def test_redirect_if_order_is_empty(self):
        self.unpaid_order = prepare_order(self.cart)
        response = self.get_from_page()
        self.assertRedirects(response, reverse_lazy('market_app:cart'))

    def test_get_404_error_if_order_does_not_exist(self):
        response = self.get_from_page()
        self.assertEqual(response.status_code, 404)

    def test_permission_denied_if_not_logged_in(self):
        self.log_in_as_customer()
        self.unpaid_order = prepare_order(self.cart)
        self.client.logout()
        response = self.get_from_page()
        self.assertEqual(response.status_code, 403)

    def test_permission_denied_if_user_id_does_not_equal_order_owner_id(self):
        self.unpaid_order = prepare_order(self.cart)
        self.customer = User.objects.get(username='customer_7')
        self.assertTrue(self.log_in_as_customer())
        response = self.get_from_page()
        self.assertEqual(response.status_code, 403)

    def test_correct_template(self):
        self.fill_cart({'1': 1})
        self.unpaid_order = prepare_order(self.cart)
        self._test_correct_template()

    def test_can_post_valid_data(self):
        self.fill_cart({'1': 1})
        top_up_balance(self.user, Decimal('32.13333'))
        self.unpaid_order = prepare_order(self.cart)
        self.assertFalse(self.unpaid_order.operation_id)
        self.post_to_page(data=self.post_data)
        self.unpaid_order.refresh_from_db()
        self.assertTrue(self.unpaid_order.operation_id)
        self.assertEqual(self.user.balance.amount, 0)

    def test_cannot_post_if_user_id_does_not_equal_order_owner_id(self):
        self.fill_cart({'1': 1})
        self.unpaid_order = prepare_order(self.cart)
        self.customer = User.objects.get(username='customer_7')
        self.assertTrue(self.log_in_as_customer())
        self.assertFalse(self.unpaid_order.operation_id)
        response = self.post_to_page(data=self.post_data)
        self.unpaid_order.refresh_from_db()
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.unpaid_order.operation_id)

    def test_is_purchasing_successful(self):
        top_up_balance(self.user, 10000)
        self.prepare_order({'1': 5, '2': 3, '7': 2})
        self.assertEqual(self.user.balance.amount, 10000)
        self.assertEqual(self.sellers.get(id=1).balance.amount, 0)
        self.assertEqual(self.sellers.get(id=2).balance.amount, 0)
        response = self.post_to_page(data=self.post_data)
        self.assertEqual(self.user.balance.amount, 9000)
        self.assertEqual(self.sellers.get(id=1).balance.amount, 800)
        self.assertEqual(self.sellers.get(id=2).balance.amount, 200)
        self.assertRedirects(response, self.ViewClass.success_url)

    def test_top_up_if_user_does_not_have_enough_money(self):
        self.assertFalse(self.user.operations.exists())
        top_up_balance(self.user, 300)
        self.prepare_order({'1': 5, '7': 2})
        self.post_to_page(data=self.post_data)
        self.assertTrue(self.user.operations.filter(amount=400).exists())

    def test_sellers_cant_buy_their_own_products(self):
        self.log_in_as_seller()
        top_up_balance(self.user, 2000)
        own_product_type_units_count_at_start = ProductType.objects.get(pk=1).units_count
        units_to_buy = {'1': 5, '7': 3}
        self.prepare_order(units_to_buy)
        self.post_to_page(data=self.post_data)
        own_product_type_units_count_at_end = ProductType.objects.get(pk=1).units_count
        self.assertEqual(own_product_type_units_count_at_start, own_product_type_units_count_at_end)
        self.assertEqual(self.user.orders.first().total_price, 300)

    def _test_use_coupon(self, expected_balance_amount, max_discount=None):
        top_up_balance(self.user, 2000)
        units_to_add = {'1': 5, '4': 1, '8': 4}
        coupon = self.create_and_set_coupon(discount_percent=10, max_discount=max_discount)
        order = self.prepare_order(units_to_add)
        order.set_coupon(coupon)
        self.post_to_page(data=self.post_data)
        self.assertEqual(self.balance.amount, expected_balance_amount)

    def test_use_coupon_without_discount_limit(self):
        self._test_use_coupon(1100)

    def test_use_coupon_with_discount_limit(self):
        self._test_use_coupon(1080, max_discount=80)

    def test_coupon_discount_dont_affect_to_seller_top_up_operation(self):
        self._test_use_coupon(1080, max_discount=80)
        self.assertEqual(self.sellers.get(pk=1).balance.amount, 600)
        self.assertEqual(self.sellers.get(pk=2).balance.amount, 400)


class OperationHistoryTest(ViewTestMixin, TestBaseWithFilledCatalogue):
    ViewClass = OperationHistoryView
    page_url = reverse_lazy('market_app:operation_history')

    def setUp(self) -> None:
        super(OperationHistoryTest, self).setUp()
        self.log_in_as_customer()
        top_up_balance(self.user, 10000)
        self.fill_cart({'1': 2, '3': 1, '7': 1})
        order = prepare_order(self.cart)
        make_purchase(order, self.user)

    def test_redirect_if_not_logged_in(self):
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_customer()
        self._test_correct_template()


class OrderDetailTest(ViewTestMixin, TestBaseWithFilledCatalogue):
    ViewClass = OrderDetail

    def setUp(self) -> None:
        super(OrderDetailTest, self).setUp()
        self.log_in_as_customer()
        top_up_balance(self.user, 10000)
        self.fill_cart({'1': 2, '3': 1, '5': 1})
        self._order = prepare_order(self.cart)

    def get_url(self, pk=None):
        if pk is None:
            return self.order.get_absolute_url()
        return Operation.objects.get(pk=pk).get_absolute_url()

    def test_redirect_if_not_logged_in(self):
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_customer()
        self._test_correct_template()

    def test_another_user_cant_see_details(self):
        another_user_data = {'username': 'AnotherCustomer', 'password': self.password}
        self.client.logout()
        self.create_customer(**another_user_data)
        self.client.login(**another_user_data)
        response = self.get_from_page()
        self.assertEqual(response.status_code, 403)


class UserMarketViewTest(ViewTestMixin, TestBaseWithFilledCatalogue):
    ViewClass = UserMarketView
    page_url = reverse_lazy('market_app:user_market')

    def test_redirect_if_not_logged_in(self):
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_seller()
        self._test_correct_template()

    def test_redirects_if_user_has_not_market(self):
        self.log_in_as_customer()
        response = self.get_from_page()
        self.assertRedirects(response, reverse_lazy('market_app:create_market'))


class ShippingPageView(ViewTestMixin, TestBaseWithFilledCatalogue):
    ViewClass = ShippingPage

    def get_url(self):
        return reverse_lazy('market_app:shipping', kwargs={'pk': self.market.pk})

    def test_redirect_if_not_logged_in(self):
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_seller()
        self._test_correct_template()

    def test_display_order_items(self):
        self._init_orders()
        self.log_in_as_seller()
        order_items = self.get_order_items()
        response = self.get_from_page()
        self.assertTrue(order_items)
        for order_item in order_items:
            self.assertContains(response, f'id="order_item_{order_item.pk}"')
            self.assertContains(response, f'{order_item.product_type.properties_as_str}')

    def test_do_not_display_order_items_from_other_markets(self):
        self._init_orders()
        self.log_in_as_seller()
        other_order_items_pks = OrderItem.objects.filter(
            ~Q(payment__user_id=self.market.pk)).values_list('pk', flat=True)
        response = self.get_from_page()
        self.assertTrue(other_order_items_pks)
        for pk in other_order_items_pks:
            self.assertNotContains(response, f'id="order_item_{pk}"')

    def test_can_mark_as_shipped(self):
        self._init_orders()
        self.log_in_as_seller()
        order_items = self.get_order_items()
        self.assertFalse(self.all_items_are_shipped(order_items.values_list('pk', flat=True)))
        items_to_mark_pks = order_items.filter(product_type_id__in=(3, 5)).values_list('pk', flat=True)
        items_not_to_mark_pks = order_items.exclude(product_type_id__in=(3, 5)).values_list('pk', flat=True)
        self.assertTrue(items_to_mark_pks)
        self.assertTrue(items_not_to_mark_pks)
        self.post_to_page(data={f'item_{pk}': 'on' for pk in items_to_mark_pks})
        self.assertTrue(self.all_items_are_shipped(items_to_mark_pks))
        self.assertFalse(self.all_items_are_shipped(items_not_to_mark_pks))

    def test_cannot_mark_as_unshipped(self):
        self._init_orders()
        self.log_in_as_seller()
        order_items = self.get_order_items()
        order_items.update(is_shipped=True)
        items_to_unmark_pks = order_items.filter(product_type_id__in=(3, 5)).values_list('pk', flat=True)
        self.post_to_page(data={f'item_{pk}': 'off' for pk in items_to_unmark_pks})
        self.assertTrue(self.all_items_are_shipped(items_to_unmark_pks))

    def test_order_changed_his_status(self):
        self._init_orders()
        self.log_in_as_seller()
        self.assertEqual(self.order_1.status, OrderStatusChoices.HAS_PAID)
        items_to_mark_pks = self.order_1.items.values_list('pk', flat=True)
        self.post_to_page(data={f'item_{pk}': 'on' for pk in items_to_mark_pks})
        self.assertEqual(self.order_1.status, OrderStatusChoices.SHIPPED)
