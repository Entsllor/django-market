import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Model, QuerySet
from django.db.models.base import ModelBase
from django.db.models.signals import post_save
from django.test import TransactionTestCase

from currencies.models import Currency
from market_app.models import Product, Market, ProductCategory, ProductType, Coupon, Cart, Balance, OrderItem, Order
from market_app.services import prepare_order, top_up_balance, make_purchase


def assert_difference(expected_difference):
    def decorator(test_function):
        def wrapper(self, *args, **kwargs):
            start_data = self.check_data_to_compare()
            test_function(self, *args, **kwargs)
            end_data = self.check_data_to_compare()
            if isinstance(expected_difference, dict):
                expected_data = start_data.copy()
                expected_data.update(expected_difference)
            else:
                expected_data = start_data + expected_difference
            self.assertEqual(end_data, expected_data)

        return wrapper

    return decorator


class BaseMarketTestCase(TransactionTestCase):
    reset_sequences = True
    default_password = 'Pass4TestUser'  # password for all accounts
    _user = None

    def setUp(self) -> None:
        self._customer = self.create_customer()
        self._seller = self.create_seller()
        self._category = self.create_category()
        self._market = self.create_market(owner=self.seller)

    def tearDown(self) -> None:
        cache.clear()

    @staticmethod
    def create_currencies():
        rates = {code: 50 for code in settings.EXTRA_CURRENCIES}
        rates[settings.DEFAULT_CURRENCY_CODE] = 1
        for currency_code in settings.CURRENCIES:
            Currency.objects.update_or_create(
                code=currency_code,
                sym=settings.CURRENCIES_SYMBOLS.get(currency_code, '?'),
                rate=rates[currency_code]
            )

    def log_in_as_customer(self) -> bool:
        return self.log_in_as(self.customer)

    def log_in_as_seller(self) -> bool:
        return self.log_in_as(self.seller)

    def log_in_as(self, user) -> bool:
        if not user.password:
            user.set_password(self.default_password)
            user.save()
        logged_in = self.client.login(username=user.username, password=self.default_password)
        self._user = user
        return logged_in

    @property
    def user(self) -> User:
        return User.objects.get(pk=self._user.pk)

    @property
    def super_user(self):
        if not hasattr(self, '_super_user'):
            self._super_user = User.objects.create_superuser("TestSuperUser", password=self.default_password)
        return User.objects.get(pk=self._super_user.pk)

    def create_customer(self, username='customer', password=None):
        if password is None:
            password = self.default_password
        customer = User.objects.create_user(username=username, password=password)
        return customer

    def create_seller(self, username='seller', password=None):
        seller = self.create_customer(username=username, password=password)
        return seller

    def assertObjectDoesNotExist(self, query_set, **kwargs):
        """Fail if an object matching the given keyword arguments exists"""
        if isinstance(query_set, (Model, ModelBase)):
            query_set = query_set.objects
        with self.assertRaises(ObjectDoesNotExist):
            return query_set.get(**kwargs)

    def create_market(self, **kwargs):
        if 'owner' not in kwargs:
            kwargs['owner'] = self.user
        market = Market.objects.create(**kwargs)
        return market

    @staticmethod
    def create_category(name='category_1'):
        category = ProductCategory.objects.create(name=name)
        return category

    def create_product(self, name='TestProduct', description='Description',
                       market=None, original_price=100, discount_percent=0,
                       category=None, available=True) -> Product:
        if market is None:
            market = self.market
        if category is None:
            category = self.category
        product = Product.objects.create(
            name=name, description=description, market=market,
            original_price=original_price, discount_percent=discount_percent,
            available=available, category=category
        )
        return product

    @staticmethod
    def _init_users(id_list, name_prefix='user_'):
        users = User.objects.bulk_create(
            objs=[User(id=i_id, username=f'{name_prefix}{i_id}') for i_id in id_list]
        )
        for user in users:
            post_save.send(user.__class__, instance=user, created=datetime.datetime.now())
        return users

    @staticmethod
    def _init_products(data):
        products = [
            Product(
                id=product_id,
                name=f'product_{product_id}',
                **values['product_data']
            ) for product_id, values in data.items()]
        Product.objects.bulk_create(objs=products)

    @staticmethod
    def _init_markets(sellers):
        markets = [
            Market(id=seller.pk, name=f'market_{seller.pk}', owner=seller) for seller in sellers
        ]
        Market.objects.bulk_create(markets)
        return markets

    @staticmethod
    def _init_categories(id_range):
        categories = [
            ProductCategory(id=i_id, name=f'Category_{i_id}') for i_id in id_range
        ]
        ProductCategory.objects.bulk_create(categories)
        return categories

    @staticmethod
    def _init_product_types(data):
        types = []
        for product_id, values in data.items():
            for type_id, type_data in values['types_data'].items():
                types.append(ProductType(product_id=product_id, id=type_id, **type_data))
        ProductType.objects.bulk_create(types)

    def create_and_set_coupon(self, discount_percent=0, discount_limit=0) -> Coupon:
        coupon = Coupon.objects.create(discount_percent=discount_percent, discount_limit=discount_limit)
        coupon.customers.add(self.user)
        return coupon

    @property
    def order(self):
        if hasattr(self, '_order'):
            return Order.objects.get(pk=self._order.pk)

    @property
    def market(self):
        return Market.objects.get(owner=self.seller)

    @property
    def markets(self):
        return Market.objects.all()

    @property
    def sellers(self):
        return User.objects.filter(market__isnull=False)

    @property
    def seller(self):
        return User.objects.get(pk=self._seller.pk)

    @property
    def customer(self):
        return User.objects.get(pk=self._customer.pk)

    @property
    def category(self):
        return ProductCategory.objects.get(pk=self._category.pk)

    @property
    def customers(self):
        return User.objects.filter(market__isnull=True)

    @property
    def products(self):
        return Product.objects.all()

    @property
    def cart(self) -> Cart:
        return Cart.objects.get(user_id=self._user.id)

    @property
    def balance(self):
        return Balance.objects.get(user_id=self._user.id)

    @property
    def product_types(self):
        return ProductType.objects.all()

    def get_order_items_that_ready_to_shipping(self) -> QuerySet[OrderItem]:
        return OrderItem.objects.select_related(
            'product_type', 'product_type__product', 'product_type__product__market', 'payment', 'order'
        ).filter(payment__user_id=self.market.owner_id)

    @staticmethod
    def are_items_shipped(ids):
        return not OrderItem.objects.filter(id__in=ids, is_shipped=False).exists()

    def fill_cart(self, types_to_add):
        cart = self.cart
        for product_type_id, units_count in types_to_add.items():
            cart.set_item(product_type_pk=product_type_id, quantity=units_count, commit=False)
        cart.save()

    def prepare_order(self, order_items: dict = None) -> Order:
        if order_items is None:
            order_items = {}
        Cart.objects.filter(pk=self.cart.pk).update(items=order_items)
        self._order = prepare_order(self.cart)
        return self._order


class FilledCatalogueMixin:
    _default_product_price = 100
    _product_data = {
        # product_id: {**product_data}
        '1': {
            'product_data': {
                'market_id': 1,
                'category_id': 1,
                'original_price': _default_product_price
            },
            'types_data': {
                # type_id: {**product_type_data}
                '1': {'units_count': 10},
                '2': {'units_count': 5},
                '3': {'units_count': 0}
            }
        },
        '2': {
            'product_data': {
                'market_id': 1,
                'category_id': 1,
                'original_price': _default_product_price
            },
            'types_data': {
                '4': {'units_count': 10},
                '5': {'units_count': 5},
                '6': {'units_count': 0}
            }
        },
        '3': {
            'product_data': {
                'market_id': 2,
                'category_id': 1,
                'original_price': _default_product_price
            },
            'types_data': {
                '7': {'units_count': 10},
                '8': {'units_count': 5},
                '9': {'units_count': 0}
            }
        },
        '4': {
            'product_data': {
                'market_id': 2,
                'category_id': 2,
                'original_price': _default_product_price
            },
            'types_data': {
                '10': {'units_count': 10},
                '11': {'units_count': 5},
                '12': {'units_count': 0}
            }
        },
        '5': {
            'product_data': {
                'market_id': 3,
                'category_id': 2,
                'original_price': _default_product_price
            },
            'types_data': {
                '13': {'units_count': 10},
                '14': {'units_count': 5},
                '15': {'units_count': 0}
            }
        },
        '6': {
            'product_data': {
                'market_id': 3,
                'category_id': 2,
                'original_price': _default_product_price
            },
            'types_data': {
                '16': {'units_count': 10},
                '17': {'units_count': 5},
                '18': {'units_count': 0}
            }
        },
        '7': {
            'product_data': {
                'market_id': 4,
                'category_id': 2,
                'original_price': _default_product_price
            },
            'types_data': {
                '19': {'units_count': 10},
                '20': {'units_count': 5},
                '21': {'units_count': 0}
            }
        },
        '8': {
            'product_data': {
                'market_id': 4,
                'category_id': 3,
                'original_price': _default_product_price
            },
            'types_data': {
                '22': {'units_count': 10},
                '23': {'units_count': 5},
                '24': {'units_count': 0}
            }
        },
    }
    _categories_count = 3
    _sellers_count = 5
    _customers_count = 2


class TestBaseWithFilledCatalogue(FilledCatalogueMixin, BaseMarketTestCase):
    def setUp(self) -> None:
        assert not User.objects.exists()
        assert not ProductType.objects.exists()
        assert not ProductCategory.objects.exists()
        assert not Product.objects.exists()
        assert not Market.objects.exists()
        self._init_categories(range(1, self._categories_count + 1))
        self._category = ProductCategory.objects.get(id=1)
        sellers = self._init_users(range(1, 6), name_prefix='seller_')
        self._init_markets(sellers)
        self._seller = self.sellers.get(id=1)
        self._init_products(self._product_data)
        self._init_product_types(self._product_data)
        self._init_users(
            range(self._sellers_count + 1, self._sellers_count + self._customers_count + 1), name_prefix='customer_')
        self._customer = self.customers.get(pk=6)

    def _init_orders(self):
        user_at_start = self._user
        self.log_in_as(User.objects.get(username=f'customer_{self._sellers_count + 1}'))
        top_up_balance(self.user.id, 10000)
        self.order_1 = self.prepare_order({'1': 2, '3': 1})
        make_purchase(self.order_1)
        self.order_2 = self.prepare_order({'1': 5, '3': 2, '5': 4, '8': 4})
        make_purchase(self.order_2)
        self.log_in_as(User.objects.get(username=f'customer_{self._sellers_count + 2}'))
        top_up_balance(self.user.id, 700)
        self.order_3 = self.prepare_order({'4': 3, '13': 3})
        make_purchase(self.order_3)
        if user_at_start:
            self.log_in_as(user_at_start)
