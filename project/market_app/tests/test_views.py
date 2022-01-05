from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.test import TransactionTestCase
from django.urls import reverse_lazy

from currencies.services import DEFAULT_CURRENCY_CODE, exchange_to
from .base_case import BaseMarketTestCase, assert_difference, TestBaseWithFilledCatalogue
from ..models import Market, Product, ProductCategory, Operation, ProductType, Order, OrderItem, OrderStatusChoices, \
    User, Coupon
from ..services import top_up_balance, make_purchase, prepare_order
from ..views import ProductCreateView, ProductEditView, CatalogueView, MarketEditView, \
    MarketCreateView, CartView, CheckOutView, TopUpView, OperationHistoryView, \
    OrderDetail, ProductTypeEdit, UserMarketView, ShippingPage, PayingView, SearchProducts, ProductView, \
    UserCouponListView


def prepare_product_data_to_post(data) -> dict:
    data = data.copy()
    market = data.get('market')
    category = data.get('category')
    if market and isinstance(market, Market):
        data['market'] = market.id
    if category and isinstance(category, ProductCategory):
        data['category'] = category.id
    return data


class ViewTestMixin(TransactionTestCase):
    reset_sequences = True
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


class ProductViewTest(ViewTestMixin, TestBaseWithFilledCatalogue):
    ViewClass = ProductView

    def setUp(self) -> None:
        super(ProductViewTest, self).setUp()
        self.product = self.products.get(id=1)
        self.log_in_as_customer()

    def get_url(self):
        return self.product.get_absolute_url()

    def test_correct_template(self):
        self._test_correct_template()

    def test_can_add_to_cart(self):
        self.assertEqual(self.cart.items, {})
        self.post_to_page(data={'product_type': 1, 'quantity': 3})
        self.assertEqual(self.cart.items, {'1': 3})

    def test_can_add_to_cart_different_types(self):
        self.assertEqual(self.cart.items, {})
        self.post_to_page(data={'product_type': 1, 'quantity': 3})
        self.post_to_page(data={'product_type': 2, 'quantity': 5})
        self.assertEqual(self.cart.items, {'1': 3, '2': 5})

    def test_cannot_add_if_units_count_equals_zero(self):
        self.assertEqual(ProductType.objects.get(pk=3).units_count, 0)
        self.assertEqual(self.cart.items, {})
        self.post_to_page(data={'product_type': 3, 'quantity': 1})
        self.assertEqual(self.cart.items, {})

    def test_cannot_add_negative_quantity(self):
        self.assertEqual(self.cart.items, {})
        self.post_to_page(data={'product_type': 1, 'quantity': 2})
        response = self.post_to_page(data={'product_type': 2, 'quantity': -2})
        self.assertFalse(response.context_data['form'].is_valid())
        self.assertEqual(self.cart.items, {'1': 2})

    def test_cannot_add_types_from_not_relevant_product(self):
        self.assertEqual(self.cart.items, {})
        self.post_to_page(data={'product_type': 1, 'quantity': 2})
        response = self.post_to_page(data={'product_type': 4, 'quantity': 1})
        self.assertFalse(response.context_data['form'].is_valid())
        self.assertEqual(self.cart.items, {'1': 2})

    def test_can_change_amount_on_cart(self):
        self.assertEqual(self.cart.items, {})
        self.post_to_page(data={'product_type': 1, 'quantity': 3})
        self.post_to_page(data={'product_type': 1, 'quantity': 2})
        self.assertEqual(self.cart.items, {'1': 2})

    def test_redirect_if_unauthenticated_user_try_to_add_to_cart(self):
        self.client.logout()
        self.assertEqual(self.cart.items, {})
        response = self.post_to_page(data={'product_type': 1, 'quantity': 3})
        self.assertRedirectsAuth(response)

    def test_redirect_if_post(self):
        response = self.post_to_page(data={'product_type': 1, 'quantity': 3})
        self.assertRedirects(response, self.ViewClass.success_url)


class ProductCreateTest(ViewTestMixin, BaseMarketTestCase):
    ViewClass = ProductCreateView
    page_url = reverse_lazy('market_app:create_product')

    def setUp(self) -> None:
        self.create_currencies()
        super(ProductCreateTest, self).setUp()
        self.created_product = None
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
        self.set_created_product(name=data['name'])
        return response

    def set_created_product(self, **data):
        self.created_product = Product.objects.filter(**data).first() or None

    def test_can_create_product(self):
        self.log_in_as_seller()
        self.post_to_product_create()
        self.assertTrue(self.created_product)
        for key in self.product_data:
            self.assertEqual(getattr(self.created_product, key), self.product_data[key])

    def test_cannot_post_if_logged_out(self):
        self.client.logout()
        response = self.post_to_product_create()
        self.assertRedirectsAuth(response)
        self.assertIsNone(self.created_product)

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
        self.new_category = self.create_category('NewProductCategory')
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

    def test_cannot_post_if_logged_out(self):
        self.client.logout()
        self.assertEqual(self.product.name, self.old_data['name'])
        response = self.post_to_product_edit(self.product.id, self.new_data)
        self.assertRedirectsAuth(response)
        for key in self.new_data:
            self.assertEqual(getattr(self.product, key), self.old_data[key])

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

    def test_cannot_edit_price_in_another_currency(self):
        self.log_in_as_seller()
        price_at_start = self.product.original_price
        response = self.post_to_product_edit(
            self.product.id, data_to_update={'original_price': 200}, currency_code='INVALID')
        self.assertIn('currency_code', response.context_data['form'].errors)
        self.assertEqual(self.product.original_price, price_at_start)

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

    def test_cannot_post_if_logged_out(self):
        self.client.logout()
        response = self.post_to_market_edit(market=self.market)
        self.assertRedirectsAuth(response)
        for key in self.new_data:
            self.assertEqual(getattr(self.market, key), self.old_data[key])

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
            self.assertEqual(getattr(self.market, key), self.old_data[key])
        self.assertEqual(response.status_code, 403)

    def test_can_another_seller_edit_side_market(self):
        another_seller = self.create_seller(username="AnotherSeller")
        self.client.login(username=another_seller, password=self.password)
        response = self.post_to_market_edit(market=self.market)
        for key in self.new_data:
            self.assertEqual(getattr(self.market, key), self.old_data[key])
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

    def test_cannot_post_if_logged_out(self):
        self.client.logout()
        response = self.post_to_market_create()
        self.assertEqual(self.created_market, None)
        self.assertFalse(Market.objects.exists())
        self.assertRedirectsAuth(response)

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

    @assert_difference(0)
    def test_cannot_post_if_logged_out(self):
        units_count = 10
        self.client.logout()
        response = self.post_to_edit_type(pk=self.product.pk, units_count=units_count)
        self.assertRedirectsAuth(response)

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

    def test_cannot_post_if_logged_out(self):
        orders_count_at_start = Order.objects.count()
        order_items_count_at_start = OrderItem.objects.count()
        order_items = {'1': 5, '2': 3, '7': 5}
        self.client.logout()
        response = self.post_to_page(data=order_items)
        self.assertRedirectsAuth(response)
        orders_count_after_post = Order.objects.count()
        order_items_count_after_post = OrderItem.objects.count()
        self.assertEqual(orders_count_at_start, orders_count_after_post)
        self.assertEqual(order_items_count_at_start, order_items_count_after_post)

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

    def test_can_change_coupon(self):
        self.assertIsNone(self.order.coupon)
        self.post_to_page(extra_data={'coupon': '1'})
        self.assertTrue(self.order.coupon)

    def test_cannot_post_if_logged_out(self):
        self.assertIsNone(self.order.coupon)
        self.client.logout()
        response = self.post_to_page(extra_data={'coupon': '1'})
        self.assertRedirectsAuth(response)
        self.assertIsNone(self.order.coupon)


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

    def test_create_one_operation(self):
        self.log_in_as_customer()
        operations_count_at_start = Operation.objects.count()
        data = self.get_top_up_form_data(1000)
        self.post_to_page(data=data)
        operations_count_after_post = Operation.objects.count()
        self.assertEqual(operations_count_at_start + 1, operations_count_after_post)

    def test_cannot_post_if_logged_out(self):
        operations_count_at_start = Operation.objects.count()
        self.client.logout()
        data = self.get_top_up_form_data(1000)
        response = self.post_to_page(data=data)
        operations_count_after_post = Operation.objects.count()
        self.assertEqual(operations_count_at_start, operations_count_after_post)
        self.assertRedirectsAuth(response)

    def test_redirect_to_unpaid_order_if_exists(self):
        self.log_in_as_customer()
        self.fill_cart({'1': 2, '7': 3})
        order = prepare_order(self.cart)
        top_up_form_data = self.get_top_up_form_data(1000)
        response = self.post_to_page(data=top_up_form_data)
        self.assertRedirects(response, reverse_lazy('market_app:checkout', kwargs={'pk': order.pk}))


class PayingTest(ViewTestMixin, TestBaseWithFilledCatalogue):
    ViewClass = PayingView
    agreement_post_data = {'agreement': 'on'}
    test_credit_cart_data = {
        'name_on_card': 'SURNAME FIRSTNAME',
        'card_number': '9999_9999_9999_9999',
    }

    def setUp(self) -> None:
        super(PayingTest, self).setUp()
        self._order = None
        self.log_in_as_customer()
        self.assertEqual(self.balance.amount, 0)
        self.assertEqual(self.sellers.get(id=1).balance.amount, 0)
        self.assertEqual(self.sellers.get(id=2).balance.amount, 0)

    def get_url(self):
        return reverse_lazy('market_app:paying', kwargs={'pk': 1})

    def test_return_404_error_if_order_does_not_exist(self):
        response = self.get_from_page()
        self.assertEqual(response.status_code, 404)

    def assertSuccessPurchase(self, order: Order):
        self.assertTrue(self.order.has_paid)
        for item in order.items.all():
            total_item_price = item.product_type.sale_price * item.amount
            self.assertEqual(item.payment.amount, total_item_price)
        self.assertTrue(order.operation.amount, order.total_price)

    def test_permission_denied_if_not_logged_in(self):
        units_to_buy = {'1': 1}
        self.log_in_as_customer()
        self.prepare_order(units_to_buy)
        self.client.logout()
        response = self.get_from_page()
        self.assertEqual(response.status_code, 403)

    def test_cannot_post_if_user_id_does_not_equal_order_owner_id(self):
        units_to_buy = {'1': 1}
        self.prepare_order(units_to_buy)
        self.customer = User.objects.get(username='customer_7')
        self.assertTrue(self.log_in_as_customer())
        self.assertFalse(self.order.operation_id)
        response = self.post_to_page(data=self.test_credit_cart_data)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.order.operation_id)

    def test_correct_template(self):
        units_to_buy = {'1': 1}
        self.prepare_order(units_to_buy)
        self._test_correct_template()

    def test_cannot_post_if_logged_out(self):
        units_to_buy = {'1': 1}
        top_up_balance(self.user.id, Decimal('32.13333'))
        self.prepare_order(units_to_buy)
        self.client.logout()
        response = self.post_to_page(data=self.test_credit_cart_data)
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(self.order.operation_id)

    def test_is_purchasing_successful(self):
        top_up_balance(self.user.id, 10000)
        self.prepare_order({'1': 5, '2': 3, '7': 2})
        response = self.post_to_page(data=self.agreement_post_data)
        self.assertEqual(self.user.balance.amount, 9000)
        self.assertSuccessPurchase(self.order)
        self.assertRedirects(response, self.ViewClass.success_url)

    def test_top_up_if_user_does_not_have_enough_money(self):
        top_up_balance(self.user.id, 300)
        self.assertEqual(self.balance.amount, 300)
        self.prepare_order({'1': 5, '7': 2})
        self.assertFalse(self.order.has_paid)
        self.post_to_page(data=self.test_credit_cart_data)
        self.assertTrue(self.user.operations.filter(amount=400).exists())
        self.assertEqual(self.balance.amount, 0)
        self.assertSuccessPurchase(self.order)

    def test_top_up_if_user_balance_is_zero(self):
        self.prepare_order({'1': 5, '7': 2})
        self.assertFalse(self.order.has_paid)
        self.post_to_page(data=self.test_credit_cart_data)
        self.assertTrue(self.user.operations.filter(amount=700).exists())
        self.assertEqual(self.balance.amount, 0)
        self.assertSuccessPurchase(self.order)


class OperationHistoryTest(ViewTestMixin, TestBaseWithFilledCatalogue):
    ViewClass = OperationHistoryView
    page_url = reverse_lazy('market_app:operation_history')

    def setUp(self) -> None:
        super(OperationHistoryTest, self).setUp()
        self.log_in_as_customer()
        top_up_balance(self.user.id, 10000)
        self.fill_cart({'1': 2, '3': 1, '7': 1})
        order = prepare_order(self.cart)
        make_purchase(order)

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
        top_up_balance(self.user.id, 10000)
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
        self.client.logout()
        self.customer = self.customers.filter(~Q(id=self.order.user_id)).first()
        self.log_in_as_customer()
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


class ShippingPageTest(ViewTestMixin, TestBaseWithFilledCatalogue):
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
        order_items = self.get_order_items_that_ready_to_shipping()
        response = self.get_from_page()
        self.assertTrue(order_items)
        for order_item in order_items:
            self.assertContains(response, f'id="order_item_{order_item.pk}"')
            self.assertContains(response, f'{order_item.product_type.properties_as_str}')

    def test_display_only_paid_items(self):
        self._init_orders()
        self.log_in_as_seller()
        order_items = self.get_order_items_that_ready_to_shipping()
        order_items.update(payment=None)
        response = self.get_from_page()
        for order_item in OrderItem.objects.all():
            self.assertNotContains(response, f'id="order_item_{order_item.pk}"')

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
        order_items = self.get_order_items_that_ready_to_shipping()
        self.assertFalse(any(order_items.values_list('is_shipped', flat=True)))
        items_to_mark_pks = order_items.filter(product_type_id__in=(3, 5)).values_list('pk', flat=True)
        items_not_to_mark_pks = order_items.exclude(product_type_id__in=(3, 5)).values_list('pk', flat=True)
        self.assertTrue(items_to_mark_pks)
        self.assertTrue(items_not_to_mark_pks)
        self.post_to_page(data={f'item_{pk}': 'on' for pk in items_to_mark_pks})
        self.assertTrue(self.all_items_are_shipped(items_to_mark_pks))
        self.assertFalse(any(order_items.filter(id__in=items_not_to_mark_pks).values_list('is_shipped', flat=True)))

    def test_cannot_post_if_logged_out(self):
        self._init_orders()
        self.client.logout()
        order_items = self.get_order_items_that_ready_to_shipping()
        self.assertFalse(any(order_items.values_list('is_shipped', flat=True)))
        items_to_mark_pks = order_items.filter(product_type_id__in=(3, 5)).values_list('pk', flat=True)
        items_not_to_mark_pks = order_items.exclude(product_type_id__in=(3, 5)).values_list('pk', flat=True)
        self.assertTrue(items_to_mark_pks)
        self.assertTrue(items_not_to_mark_pks)
        response = self.post_to_page(data={f'item_{pk}': 'on' for pk in items_to_mark_pks})
        self.assertRedirectsAuth(response)
        self.assertFalse(any(order_items.values_list('is_shipped', flat=True)))

    def test_cannot_mark_as_unshipped(self):
        self._init_orders()
        self.log_in_as_seller()
        order_items = self.get_order_items_that_ready_to_shipping()
        order_items.update(is_shipped=True)
        items_to_unmark_pks = order_items.filter(product_type_id__in=(3, 5)).values_list('pk', flat=True)
        self.post_to_page(data={f'item_{pk}': 'off' for pk in items_to_unmark_pks})
        self.assertTrue(self.all_items_are_shipped(items_to_unmark_pks))

    def test_order_has_changed_its_status(self):
        self._init_orders()
        self.log_in_as_seller()
        self.assertEqual(self.order_1.status, OrderStatusChoices.HAS_PAID.value)
        items_to_mark_pks = self.order_1.items.values_list('pk', flat=True)
        self.post_to_page(data={f'item_{pk}': 'on' for pk in items_to_mark_pks})
        self.assertEqual(self.order_1.status, OrderStatusChoices.SHIPPED.value)


class SearchTest(ViewTestMixin, TestBaseWithFilledCatalogue):
    ViewClass = SearchProducts
    page_url = reverse_lazy('market_app:search_products')

    def test_correct_template(self):
        self._test_correct_template()

    def test_can_search_by_category(self):
        response = self.get_from_page(data={'category': 3})
        expected_names = Product.objects.filter(category_id=3).values_list('name', flat=True)
        unexpected_names = Product.objects.exclude(category_id=3).values_list('name', flat=True)
        self.assertTrue(expected_names)
        self.assertTrue(unexpected_names)
        for expected_name in expected_names:
            self.assertContains(response, expected_name)
        for unexpected_name in unexpected_names:
            self.assertNotContains(response, unexpected_name)

    def test_can_search_by_name(self):
        query_value = '2'
        response = self.get_from_page(data={'q': query_value})
        expected_names = Product.objects.filter(
            Q(description__icontains=query_value) | Q(name__icontains=query_value)
        ).values_list('name', flat=True)
        unexpected_names = Product.objects.exclude(
            Q(description__icontains=query_value) | Q(name__icontains=query_value)
        ).values_list('name', flat=True)
        self.assertTrue(expected_names)
        self.assertTrue(unexpected_names)
        for expected_name in expected_names:
            self.assertContains(response, expected_name)
        for unexpected_name in unexpected_names:
            self.assertNotContains(response, unexpected_name)


class UserCouponListTest(ViewTestMixin, BaseMarketTestCase):
    ViewClass = UserCouponListView
    page_url = reverse_lazy('market_app:user_coupons')

    def setUp(self) -> None:
        super(UserCouponListTest, self).setUp()
        coupons = [Coupon(discount_percent=10) for _ in range(5)]
        Coupon.objects.bulk_create(coupons)
        Coupon.objects.get(pk=1).customers.add(self.customer.id)
        Coupon.objects.get(pk=2).customers.add(self.customer.id)

    def test_redirect_if_not_logged_in(self):
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_customer()
        self._test_correct_template()

    def test_display_all_users_coupons(self):
        self.log_in_as_customer()
        response = self.get_from_page()
        self.assertContains(response, 'id="coupon_1_block"')
        self.assertContains(response, 'id="coupon_2_block"')

    def test_do_not_display_another_coupons(self):
        self.log_in_as_customer()
        response = self.get_from_page()
        self.assertNotContains(response, 'id="coupon_3_block"')
        self.assertNotContains(response, 'id="coupon_4_block"')
