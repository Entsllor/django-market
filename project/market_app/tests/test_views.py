from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse_lazy

from .base_case import BaseMarketTestCase, assert_difference, TestBaseWithFilledCatalogue
from ..models import Market, Product, ProductCategory
from ..services import top_up_balance, DEFAULT_CURRENCY, exchange_to


def prepare_product_data_to_post(data) -> dict:
    data = data.copy()
    market = data.get('market')
    category = data.get('category')
    if market and isinstance(market, Market):
        data['market'] = market.id
    if category and isinstance(category, ProductCategory):
        data['category'] = category.id
    return data


class ProductCreateTest(BaseMarketTestCase):
    product_create_url = reverse_lazy('market_app:create_product')

    def setUp(self) -> None:
        super(ProductCreateTest, self).setUp()
        self.market = self.create_market(owner=self.seller)
        self.product_data = {
            'name': 'TestProductName', 'description': 'text', 'market': self.market,
            'original_price': 100, 'discount_percent': 0,
            'available': True, 'category': self.category
        }

    def post_to_product_create(self, data: dict = None, extra_data: dict = None, check_unique=True, **kwargs):
        if data is None:
            data = self.product_data
        data = data.copy()
        if extra_data:
            data.update(extra_data)
        data = prepare_product_data_to_post(data)
        if check_unique:
            self.assertObjectDoesNotExist(Product.objects, name=data['name'])
        response = self.post_data(self.product_create_url, data=data, **kwargs)
        self.try_set_created_product(**data)
        return response

    def try_set_created_product(self, **data):
        try:
            self.created_product = Product.objects.get(**data)
        except ObjectDoesNotExist:
            self.created_product = None

    def test_can_create_product(self):
        self.log_in_as_seller()
        self.post_to_product_create()
        for key in self.product_data:
            self.assertEqual(self.created_product.__getattribute__(key), self.product_data[key])

    def test_invalid_data(self):
        self.log_in_as_seller()
        self.post_to_product_create(extra_data={'market': 71.2})
        self.assertIsNone(self.created_product)


class ProductEditTest(BaseMarketTestCase):
    def setUp(self) -> None:
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
        self._product.refresh_from_db()
        return self._product

    def post_to_product_edit(self, product_id: int, data_to_update: dict, currency_code=DEFAULT_CURRENCY, **kwargs):
        data_to_post = prepare_product_data_to_post(self.old_data.copy() | data_to_update)
        data_to_post.update({'currency_code': currency_code})
        return self.post_data(
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


class MarketEditTest(BaseMarketTestCase):
    def setUp(self) -> None:
        super(MarketEditTest, self).setUp()
        self.old_data = {'name': 'OldName', 'description': 'OldDescription'}
        self.new_data = {'name': 'NewName', 'description': 'NewDescription'}
        self.market = self.create_market(owner=self.seller, **self.old_data)

    def post_to_market_edit(self, market: Market, data_to_update: dict = None, **kwargs):
        if data_to_update is None:
            data_to_update = self.new_data
        response = self.post_data(
            reverse_lazy('market_app:edit_market', args=[market.id]),
            data=self.old_data.copy() | data_to_update, **kwargs
        )
        market.refresh_from_db()
        return response

    def test_can_edit_market_as_owner(self):
        self.log_in_as_seller()
        self.post_to_market_edit(market=self.market)
        for key in self.new_data:
            self.assertEqual(self.market.__getattribute__(key), self.new_data[key])

    def test_edit_market_as_customer(self):
        self.log_in_as_customer()
        response = self.post_to_market_edit(market=self.market)
        for key in self.new_data:
            self.assertNotEqual(self.market.__getattribute__(key), self.new_data[key])
        self.assertEqual(response.status_code, 403)

    def test_can_seller_edit_side_market(self):
        self.log_in_as_seller()
        another_seller = self.create_seller(username="AnotherSeller")
        another_market = self.create_market(owner=another_seller)
        response = self.post_to_market_edit(market=another_market)
        for key in self.new_data:
            self.assertNotEqual(self.market.__getattribute__(key), self.new_data[key])
        self.assertEqual(response.status_code, 403)

    def test_can_another_seller_edit_side_market(self):
        another_seller = self.create_seller(username="AnotherSeller")
        self.client.login(username=another_seller, password=self.password)
        response = self.post_to_market_edit(market=self.market)
        for key in self.new_data:
            self.assertNotEqual(self.market.__getattribute__(key), self.new_data[key])
        self.assertEqual(response.status_code, 403)


class MarketCreateViewsTest(BaseMarketTestCase):
    market_create_url = reverse_lazy('market_app:create_market')

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
        response = self.post_data(self.market_create_url, data=data, **kwargs)
        self.try_set_created_market(**data)
        return response

    def try_set_created_market(self, **data):
        try:
            self.created_market = Market.objects.get(**data)
        except ObjectDoesNotExist:
            self.created_market = None

    def test_can_create_market(self):
        self.log_in_as_seller()
        self.post_to_market_create()
        self.assertIsInstance(self.created_market, Market)
        self.assertEqual(self.created_market.owner.id, self.user.id)


class ProductTypeUnitsTest(BaseMarketTestCase):
    def setUp(self) -> None:
        super(ProductTypeUnitsTest, self).setUp()
        self._product = self.create_product()
        self._product_type = self._product.create_product_type(units_count=0)

    @property
    def product(self) -> Product:
        self._product.refresh_from_db()
        return self._product

    @property
    def product_type(self):
        self._product_type.refresh_from_db()
        return self._product_type

    def post_to_create_units(self, pk, **kwargs):
        return self.post_data(
            reverse_lazy('market_app:edit_type', kwargs={'pk': pk}),
            data=kwargs
        )

    def check_data_to_compare(self):
        return self.product_type.units_count

    @assert_difference(10)
    def test_edit_if_owner(self):
        units_count = 10
        self.log_in_as_seller()
        self.post_to_create_units(pk=self.product.pk, units_count=units_count)

    @assert_difference(0)
    def test_edit_if_not_owner(self):
        units_count = 10
        new_seller = self.create_seller(username='NewSeller')
        self.client.login(username=new_seller.username, password=self.password)
        response = self.post_to_create_units(pk=self.product.pk, units_count=units_count)
        self.assertEqual(response.status_code, 403)

    @assert_difference(0)
    def test_edit_if_customer(self):
        units_count = 10
        self.log_in_as_customer()
        response = self.post_to_create_units(pk=self.product.pk, units_count=units_count)
        self.assertEqual(response.status_code, 403)


class CartViewTest(TestBaseWithFilledCatalogue):
    page_url = reverse_lazy('market_app:cart')

    def get_from_page(self, **kwargs):
        return self.client.get(path=self.page_url, **kwargs)

    def post_to_page(self, **kwargs):
        return self.client.post(path=self.page_url, **kwargs)

    def test_redirect_if_not_logged_in(self):
        response = self.get_from_page()
        self.assertRedirects(response, reverse_lazy('accounts:log_in') + '?next=' + self.page_url)


class CheckOutPage(TestBaseWithFilledCatalogue):
    check_out_page_url = reverse_lazy('market_app:checkout')
    top_up_page_url = reverse_lazy('market_app:top_up')
    cart_page_url = reverse_lazy('market_app:cart')
    confirmation_page_url = reverse_lazy('market_app:order_confirmation')

    def get_from_page(self, **kwargs):
        return self.client.get(path=self.check_out_page_url, **kwargs)

    def post_to_page(self, **kwargs):
        return self.client.post(path=self.check_out_page_url, **kwargs)

    def test_redirect_if_user_do_not_have_enough_money(self):
        self.log_in_as_customer()
        top_up_balance(self.shopping_account, 500)
        self.fill_cart({'1': 5, '4': 5})
        response = self.get_from_page()
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.top_up_page_url)

    def test_redirect_if_users_order_list_is_empty(self):
        self.log_in_as_customer()
        top_up_balance(self.shopping_account, 500)
        response = self.get_from_page()
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.cart_page_url)

    def test_do_not_redirect_if_enough_money(self):
        self.log_in_as_customer()
        top_up_balance(self.shopping_account, 5000)
        self.fill_cart({'1': 5, '4': 5})
        response = self.get_from_page()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'market_app/checkout_page.html')

    def test_do_purchase_if_user_agrees(self):
        self.log_in_as_customer()
        top_up_balance(self.shopping_account, 1000)
        self.fill_cart({'1': 5, '4': 5})
        response = self.post_to_page(data={'agreement': True})
        self.assertRedirects(response, self.confirmation_page_url)

    def test_redirect_if_user_does_not_agree(self):
        self.log_in_as_customer()
        top_up_balance(self.shopping_account, 1000)
        self.fill_cart({'1': 5, '4': 5})
        response = self.post_to_page(data={'agreement': False})
        self.assertRedirects(response, self.cart_page_url)

    def test_is_purchasing_successful(self):
        self.log_in_as_customer()
        top_up_balance(self.shopping_account, 10000)
        self.fill_cart({'1': 5, '2': 3, '4': 2})
        self.assertEqual(self.shopping_account.balance, 10000)
        self.assertEqual(Market.objects.get(id=1).owner.shopping_account.balance, 0)
        self.assertEqual(Market.objects.get(id=2).owner.shopping_account.balance, 0)
        response = self.post_to_page(data={'agreement': True})
        self.assertEqual(self.shopping_account.balance, 9000)
        self.assertEqual(Market.objects.get(id=1).owner.shopping_account.balance, 800)
        self.assertEqual(Market.objects.get(id=2).owner.shopping_account.balance, 200)
        self.assertRedirects(response, self.confirmation_page_url)

    def test_cart_is_empty_after_purchasing(self):
        self.log_in_as_customer()
        top_up_balance(self.shopping_account, 10000)
        self.fill_cart({'1': 5, '4': 5})
        self.assertNotEqual(self.shopping_account.order, {})
        self.assertEqual(self.shopping_account.balance, 10000)
        self.post_to_page(data={'agreement': True})
        self.assertEqual(self.shopping_account.order, {})


class TopUpViewTest(BaseMarketTestCase):
    top_up_page_url = reverse_lazy('market_app:top_up')
    cart_page_url = reverse_lazy('market_app:cart')

    def get_from_page(self, **kwargs):
        return self.client.get(path=self.top_up_page_url, **kwargs)

    def post_to_page(self, **kwargs):
        return self.client.post(path=self.top_up_page_url, **kwargs)

    def test_redirect_if_not_logged_in(self):
        response = self.get_from_page()
        self.assertRedirects(response, reverse_lazy('accounts:log_in') + '?next=' + self.top_up_page_url)

    def test_can_top_up_balance(self):
        self.log_in_as_customer()
        data = {
            'name_on_card': 'FULL NAME',
            'card_number': 9999999999999999,
            'top_up_amount': 1000,
            'currency_code': DEFAULT_CURRENCY
        }
        self.assertEqual(self.user.shopping_account.balance, 0)
        response = self.post_to_page(data=data)
        self.user.shopping_account.refresh_from_db()
        self.assertEqual(self.user.shopping_account.balance, 1000)
        self.assertRedirects(response, self.cart_page_url)
