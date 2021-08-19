import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Model
from django.db.models.signals import post_save
from django.test import TestCase

from ..models import Product, Market, ProductCategory, ProductType, ShoppingAccount


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

    def setUp(self) -> None:
        self.customer = self.create_customer()
        self.seller = self.create_seller()
        self.category = self.create_category()
        self.market = self.create_market(owner=self.seller)

    @property
    def shopping_account(self) -> ShoppingAccount:
        return ShoppingAccount.objects.get(user=self.user)

    @property
    def balance(self):
        return self.shopping_account.balance

    def log_in_as_customer(self):
        self._log_in(self.customer)

    def log_in_as_seller(self):
        self._log_in(self.seller)

    def _log_in(self, user):
        if not user.password:
            user.set_password(self.password)
            user.save()
        self.client.login(username=user.username, password=self.password)
        self.user = user

    def create_customer(self, username='customer', password=None):
        if password is None:
            password = self.password
        customer = User.objects.create_user(username=username, password=password)
        return customer

    def create_seller(self, username='seller', password=None):
        seller = self.create_customer(username=username, password=password)
        return seller

    def post_data(self, url, data, **kwargs):
        return self.client.post(path=url, data=data, **kwargs)

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


class TestBaseWithFilledCatalogue(BaseMarketTestCase):
    default_product_price = 100
    catalogue_data = {
        # 'product_name': {'type_id': 'type_data'}
        '1': {'1': {'units_count': 10}, '2': {'units_count': 10}, '3': {'units_count': 10}},
        '2': {'4': {'units_count': 10}, '5': {'units_count': 10}, '6': {'units_count': 10}},
        '3': {'7': {'units_count': 5}, '8': {'units_count': 5}, '9': {'units_count': 5}},
        '4': {'10': {'units_count': 1}, '11': {'units_count': 1}, '12': {'units_count': 1}},
        '5': {'13': {'units_count': 0}, '14': {'units_count': 0}, '15': {'units_count': 0}},
    }

    def setUp(self) -> None:
        assert not User.objects.exists()
        assert not ProductType.objects.exists()
        assert not Product.objects.exists()
        assert not Market.objects.all().exists()
        self.category = self.create_category()
        self._init_users(range(1, 6), name_prefix='seller_')
        self._init_markets(range(1, 6))
        self.seller = self.sellers.get(id=1)
        self.market = self.markets.get(id=1)
        self._init_products(self.catalogue_data)
        self._init_product_types(self.catalogue_data)
        self._init_users([6, 7], name_prefix='customer_')
        self.customer = self.customers.get(pk=6)

    @staticmethod
    def _init_users(id_list, name_prefix='user_'):
        users = User.objects.bulk_create(
            objs=[User(id=i_id, username=f'{name_prefix}{i_id}') for i_id in id_list]
        )
        for user in users:
            post_save.send(user.__class__, instance=user, created=datetime.datetime.now())

    def _init_products(self, data):
        products = [Product(id=i_id, name=f'product_{i_id}', category_id=1, market_id=i_id,
                            original_price=self.default_product_price) for i_id in data.keys()]
        Product.objects.bulk_create(objs=products)

    @staticmethod
    def _init_markets(id_list):
        Market.objects.bulk_create(
            objs=[Market(id=i_id, name=f'market_{i_id}', owner_id=i_id) for i_id in id_list]
        )

    @staticmethod
    def _init_product_types(data):
        types = []
        for product_id, types_data in data.items():
            for type_id, type_data in types_data.items():
                types.append(ProductType(product_id=product_id, **type_data))
        ProductType.objects.bulk_create(types)

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

    def fill_cart(self, types_to_add):
        for product_type_id, units_count in types_to_add.items():
            self.shopping_account.set_units_count_to_order(product_type_pk=product_type_id, quantity=units_count)
