import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Model, QuerySet
from django.db.models.signals import post_save
from django.test import TestCase

from currencies.services import create_currencies_from_settings
from market_app.models import Product, Market, ProductCategory, ProductType, Coupon, Cart, Balance, OrderItem, Order
from market_app.services import prepare_order, top_up_balance, make_purchase


class FailedToCreateObject(Exception):
    """raise if failed to create an object"""


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


class BaseMarketTestCase(TestCase):
    password = 'SomePassword123/'  # password for all accounts
    _user = None

    def setUp(self) -> None:
        self.customer = self.create_customer()
        self.seller = self.create_seller()
        self.category = self.create_category()
        self.market = self.create_market(owner=self.seller)

    @property
    def cart(self) -> Cart:
        return self.user.cart

    @property
    def balance(self):
        return Balance.objects.get(pk=self.user.balance.id)

    @staticmethod
    def create_currencies():
        create_currencies_from_settings()

    def log_in_as_customer(self) -> bool:
        return self._log_in(self.customer)

    def log_in_as_seller(self) -> bool:
        return self._log_in(self.seller)

    def _log_in(self, user) -> bool:
        if not user.password:
            user.set_password(self.password)
            user.save()
        logged_in = self.client.login(username=user.username, password=self.password)
        self._user = user
        return logged_in

    @property
    def user(self) -> User:
        return User.objects.get(pk=self._user.pk)

    def create_customer(self, username='customer', password=None):
        if password is None:
            password = self.password
        customer = User.objects.create_user(username=username, password=password)
        return customer

    def create_seller(self, username='seller', password=None):
        seller = self.create_customer(username=username, password=password)
        return seller

    def assertObjectDoesNotExist(self, query_set, **kwargs):
        """Fail if an object matching the given keyword arguments exists"""
        if isinstance(query_set, Model):
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


def _create_coupon(discount_percent, max_discount):
    return Coupon.objects.create(discount_percent=discount_percent, max_discount=max_discount)


class TestBaseWithFilledCatalogue(BaseMarketTestCase):
    DEFAULT_PRODUCT_PRICE = 100
    PRODUCT_DATA = {
        # product_id: {**product_data}
        '1': {
            'product_data': {
                'market_id': 1,
                'category_id': 1,
                'original_price': DEFAULT_PRODUCT_PRICE
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
                'original_price': DEFAULT_PRODUCT_PRICE
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
                'original_price': DEFAULT_PRODUCT_PRICE
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
                'original_price': DEFAULT_PRODUCT_PRICE
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
                'original_price': DEFAULT_PRODUCT_PRICE
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
                'original_price': DEFAULT_PRODUCT_PRICE
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
                'original_price': DEFAULT_PRODUCT_PRICE
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
                'original_price': DEFAULT_PRODUCT_PRICE
            },
            'types_data': {
                '22': {'units_count': 10},
                '23': {'units_count': 5},
                '24': {'units_count': 0}
            }
        },
    }

    def setUp(self) -> None:
        assert not User.objects.exists()
        assert not ProductType.objects.exists()
        assert not Product.objects.exists()
        assert not Market.objects.exists()
        self._init_categories(range(1, 4))
        self.category = self.create_category()
        sellers = self._init_users(range(1, 5), name_prefix='seller_')
        self._init_markets(sellers)
        self.seller = self.sellers.get(id=1)
        self._init_products(self.PRODUCT_DATA)
        self._init_product_types(self.PRODUCT_DATA)
        self._init_users([6, 7], name_prefix='customer_')
        self.customer = self.customers.get(pk=6)

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
                types.append(ProductType(product_id=product_id, **type_data))
        ProductType.objects.bulk_create(types)

    def create_and_set_coupon(self, discount_percent=0, max_discount=0) -> Coupon:
        coupon = _create_coupon(discount_percent, max_discount)
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
    def customers(self):
        return User.objects.filter(market__isnull=True)

    @property
    def products(self):
        return Product.objects.all()

    @property
    def product_types(self):
        return ProductType.objects.all()

    def get_order_items_that_ready_to_shipping(self) -> QuerySet[OrderItem]:
        return OrderItem.objects.select_related(
            'product_type', 'product_type__product', 'product_type__product__market', 'payment', 'order'
        ).filter(payment__user_id=self.market.owner_id)

    @staticmethod
    def all_items_are_shipped(ids):
        return not OrderItem.objects.filter(id__in=ids, is_shipped=False).exists()

    def _init_orders(self):
        cur_user = self._user
        self._log_in(User.objects.get(username='customer_6'))
        top_up_balance(self.user, 10000)
        self.order_1 = self.prepare_order({'1': 2, '3': 1})
        make_purchase(self.order_1, self.user)
        self.order_2 = self.prepare_order({'1': 5, '3': 2, '5': 4, '8': 4})
        make_purchase(self.order_2, self.user)
        self._log_in(User.objects.get(username='customer_7'))
        top_up_balance(self.user, 700)
        self.order_3 = self.prepare_order({'4': 3, '13': 3})
        make_purchase(self.order_3, self.user)
        if cur_user:
            self._log_in(cur_user)

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
