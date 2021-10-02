from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase
from django.urls import reverse_lazy

from currencies.services import DEFAULT_CURRENCY, exchange_to
from .base_case import BaseMarketTestCase, assert_difference, TestBaseWithFilledCatalogue, FailedToCreateObject
from ..models import Market, Product, ProductCategory, Operation, ProductType, Order
from ..services import top_up_balance, make_purchase, prepare_order
from ..views import ProductCreateView, ProductEditView, CatalogueView, MarketEditView, MarketCreateView, \
    CartView, CheckOutView, TopUpView, OperationHistoryView, OrderDetail, ProductTypeEdit


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
            check_unique=True, currency_code=DEFAULT_CURRENCY, **kwargs):
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
        expected_price = exchange_to(DEFAULT_CURRENCY, 1000)
        self.assertNotEqual(expected_price, self.product_data['original_price'])
        self.post_to_product_create(extra_data={'original_price': 1000}, currency_code=DEFAULT_CURRENCY)
        real_price = self.created_product.original_price
        self.assertEqual(expected_price, real_price)

    def test_create_in_another_currency(self):
        self.log_in_as_seller()
        expected_price = exchange_to(DEFAULT_CURRENCY, 1000, _from='RUB')
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

    def post_to_product_edit(self, product_id: int, data_to_update: dict, currency_code=DEFAULT_CURRENCY, **kwargs):
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
        expected_price = exchange_to(DEFAULT_CURRENCY, 1000)
        self.assertNotEqual(expected_price, self.product.original_price)
        self.log_in_as_seller()
        self.post_to_product_edit(self.product.id, data_to_update={'original_price': 1000},
                                  currency_code=DEFAULT_CURRENCY)
        new_price = self.product.original_price
        self.assertEqual(new_price, expected_price)

    def test_edit_price_in_another_currency(self):
        expected_price = exchange_to(DEFAULT_CURRENCY, 100, _from='RUB')
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
        self.create_currencies()
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
        self.create_currencies()

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

    def test_one_user_cannot_create_two_markets(self):
        self.log_in_as_seller()
        self.post_to_market_create()
        response = self.post_to_market_create(check_unique=False)
        self.assertEqual(response.status_code, 403)

    def test_redirects_if_user_already_have_account(self):
        self.log_in_as_seller()
        self.post_to_market_create()
        response = self.get_from_page()
        self.assertRedirects(response, reverse_lazy('market_app:my_market'), target_status_code=302)

    def test_redirect_if_not_logged_in(self):
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_customer()
        self._test_correct_template()


class ProductTypeEditTest(ViewTestMixin, BaseMarketTestCase):
    ViewClass = ProductTypeEdit

    def setUp(self) -> None:
        super(ProductTypeEditTest, self).setUp()
        self.create_currencies()
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
        self.create_currencies()
        self.log_in_as_customer()

    def test_can_change_order_at_cart_page(self):
        order_items = {'1': 5, '2': 3, '4': 5}
        self.fill_cart(order_items)
        changed_order_items = {'1': 8, '2': 0, '4': 2}
        self.post_to_page(data=changed_order_items)
        order: Order = self.user.orders.first()
        self.assertEqual(order.get_units_count_of('1'), 8)
        self.assertEqual(order.get_units_count_of('4'), 2)
        self.assertFalse(order.items.filter(product_type_id='2').exists())

    def test_redirect_if_form_is_valid(self):
        order_items = {'1': 5, '2': 3, '4': 5}
        response = self.post_to_page(data=order_items)
        order = self.user.orders.first()
        self.assertRedirects(response, self.get_success_url(pk=order.pk))

    def test_redirect_if_not_logged_in(self):
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_customer()
        self._test_correct_template()


class CheckOutPageTest(ViewTestMixin, TestBaseWithFilledCatalogue):
    ViewClass = CheckOutView
    orders_list_url = reverse_lazy('market_app:orders')
    top_up_page_url = reverse_lazy('market_app:top_up')

    def setUp(self) -> None:
        super(CheckOutPageTest, self).setUp()
        self.create_currencies()
        self.log_in_as_customer()

    def get_url(self):
        return reverse_lazy('market_app:checkout', kwargs={'pk': self.order.pk})

    def post_to_page(self, data: dict = None, **kwargs):
        if data is None:
            data = {}
        elif 'address' not in data:
            data['address'] = 'Some user shipped address'
        return self.client.post(path=self.get_url(), data=data, **kwargs)

    def test_redirect_if_not_logged_in(self):
        top_up_balance(self.user, 5000)
        self.prepare_order({'1': 5, '4': 5})
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_customer()
        top_up_balance(self.user, 5000)
        self.prepare_order({'1': 5, '4': 5})
        self._test_correct_template()

    def test_redirect_if_user_do_not_have_enough_money(self):
        top_up_balance(self.user, 500)
        self.prepare_order({'1': 5, '4': 5})
        response = self.get_from_page()
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.top_up_page_url)

    def test_do_not_redirect_if_enough_money(self):
        top_up_balance(self.user, 5000)
        self.prepare_order({'1': 5, '4': 5})
        response = self.get_from_page()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'market_app/checkout_page.html')

    def test_do_purchase_if_user_agrees(self):
        top_up_balance(self.user, 1000)
        self.prepare_order({'1': 5, '4': 5})
        response = self.post_to_page(data={'agreement': 'on'})
        self.assertRedirects(response, self.ViewClass.success_url)

    def test_redirect_if_user_does_not_agree(self):
        top_up_balance(self.user, 1000)
        self.prepare_order({'1': 5, '4': 5})
        response = self.post_to_page(data={})
        self.assertRedirects(response, self.orders_list_url)

    def test_is_purchasing_successful(self):
        top_up_balance(self.user, 10000)
        self.prepare_order({'1': 5, '2': 3, '4': 2})
        self.assertEqual(self.user.balance.amount, 10000)
        self.assertEqual(self.sellers.get(id=1).balance.amount, 0)
        self.assertEqual(self.sellers.get(id=2).balance.amount, 0)
        response = self.post_to_page(data={'agreement': 'on'})
        self.assertEqual(self.user.balance.amount, 9000)
        self.assertEqual(self.sellers.get(id=1).balance.amount, 800)
        self.assertEqual(self.sellers.get(id=2).balance.amount, 200)
        self.assertRedirects(response, self.ViewClass.success_url)

    def test_cart_is_empty_after_purchasing(self):
        top_up_balance(self.user, 10000)
        self.prepare_order({'1': 5, '4': 5})
        self.assertEqual(self.user.balance.amount, 10000)
        self.post_to_page(data={'agreement': 'False'})
        self.assertEqual(self.cart.items, {})

    def test_sellers_cant_buy_their_own_products(self):
        self.log_in_as_seller()
        top_up_balance(self.user, 2000)
        own_product_type_units_count_at_start = ProductType.objects.get(pk=1).units_count
        units_to_buy = {'1': 5, '5': 3}
        self.prepare_order(units_to_buy)
        self.post_to_page()
        own_product_type_units_count_at_end = ProductType.objects.get(pk=1).units_count
        self.assertEqual(own_product_type_units_count_at_start, own_product_type_units_count_at_end)
        self.assertEqual(self.user.orders.first().total_price, 300)

    def _test_use_coupon(self, expected_amount, max_discount=None):
        top_up_balance(self.user, 2000)
        units_to_add = {'1': 5, '3': 1, '4': 4}
        self.create_and_set_coupon(discount_percent=10, max_discount=max_discount)
        self.prepare_order(units_to_add)
        self.post_to_page(data={'agreement': 'on', 'coupon': 1})
        self.assertEqual(self.balance.amount, expected_amount)

    def test_use_coupon_without_discount_limit(self):
        self._test_use_coupon(1100)

    def test_use_coupon_with_discount_limit(self):
        self._test_use_coupon(1080, max_discount=80)

    def test_coupon_discount_dont_affect_to_seller_top_up_operation(self):
        self._test_use_coupon(1080, max_discount=80)
        self.assertEqual(self.sellers.get(pk=1).balance.amount, 600)
        self.assertEqual(self.sellers.get(pk=2).balance.amount, 400)


class TopUpViewTest(ViewTestMixin, BaseMarketTestCase):
    ViewClass = TopUpView
    page_url = reverse_lazy('market_app:top_up')
    catalogue_url = reverse_lazy('market_app:catalogue')

    def setUp(self) -> None:
        self.create_currencies()
        super(TopUpViewTest, self).setUp()

    def test_redirect_if_not_logged_in(self):
        self._test_redirect_if_not_logged_in()

    def test_correct_template(self):
        self.log_in_as_customer()
        self._test_correct_template()

    def test_can_top_up_balance(self):
        self.log_in_as_customer()
        data = {
            'name_on_card': 'FULL NAME',
            'card_number': 9999999999999999,
            'top_up_amount': 1000,
            'currency_code': DEFAULT_CURRENCY
        }
        self.assertEqual(self.user.balance.amount, 0)
        response = self.post_to_page(data=data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance.amount, 1000)
        self.assertRedirects(response, self.catalogue_url)


class OperationHistoryTest(ViewTestMixin, TestBaseWithFilledCatalogue):
    ViewClass = OperationHistoryView
    page_url = reverse_lazy('market_app:operation_history')

    def setUp(self) -> None:
        super(OperationHistoryTest, self).setUp()
        self.create_currencies()
        self.log_in_as_customer()
        top_up_balance(self.user, 10000)
        self.fill_cart({'1': 2, '3': 1, '5': 1})
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
        self.order = prepare_order(self.cart)

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
