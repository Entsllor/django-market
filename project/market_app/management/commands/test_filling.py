from random import randint, sample, choice
from typing import Type

from django.core.management.base import BaseCommand
from django.db.models import Max, Model

from market_app.models import *


class Command(BaseCommand):
    help = 'Fill db with test data'

    def add_arguments(self, parser):
        parser.add_argument('custom', help='run with settings', type=str.lower)

    def handle(self, *args, **options):
        if 'custom' in options:
            fill_with_settings()
        else:
            fill()


def _zero_or_in(a, b):
    if randint(0, 1):
        return randint(a, b)
    return 0


def get_last_pk(model: Type[Model]):
    return model.objects.aggregate(Max('pk')).popitem()[1] or 0


attributes_number_range = ('10', '15', '20', '30', '40', '50', '100')
attributes = {
    'Color': ('red', 'black', 'yellow', 'pink', 'orange', 'white', 'gray', 'brown'),
    'Height': attributes_number_range,
    'Weight': attributes_number_range,
    'Diagonal': attributes_number_range,
    'Batteries included': ('true', 'false')
}


def create_categories(n=5):
    categories = []
    last_pk = get_last_pk(ProductCategory)
    for i in range(n):
        last_pk += 1
        categories.append(ProductCategory(name=f'Category_{i + last_pk}'))
    ProductCategory.objects.bulk_create(categories)


def _create_attributes(k=None):
    if k is None:
        k = randint(0, 3)
    attrs = sample(attributes.keys(), k=k) or ''
    return '\n'.join(attrs)


def _create_properties(product_obj: Product):
    properties = {}
    for attr in product_obj.attributes.split('\n'):
        if attr:
            properties[attr] = choice(attributes[attr])
    return properties


def create_markets(sellers):
    markets = []
    for seller in sellers:
        market_i = seller.pk
        name = f'Market_{market_i}'
        market = Market(owner_id=market_i, name=name, description='text' * market_i)
        markets.append(market)
    return Market.objects.bulk_create(markets)


def create_users(n=5):
    users = []
    last_pk = get_last_pk(User)
    for _ in range(n):
        last_pk += 1
        name = f'User_{last_pk}'
        user = User.objects.create_user(username=name, email='zz@zz.com', password='pass')
        users.append(user)
    return users


def create_products(markets=None):
    if markets is None:
        markets = Market.objects.all()
    elif not markets:
        return []
    elif isinstance(markets, (list, tuple)) and not markets[0].pk:
        markets_names = [market.name for market in markets]
        markets = Market.objects.filter(name__in=markets_names)
    last_pk = get_last_pk(Product)
    products = []
    for market in markets:
        for i in range(1, randint(3, 30)):
            last_pk += 1
            name = f'Product_{last_pk}'
            product = Product(
                market=market,
                name=name,
                description=name.lower(),
                original_price=randint(30, 200),
                discount_percent=_zero_or_in(1, 50),
                available=bool(randint(0, 1)),
                category_id=randint(1, ProductCategory.objects.count()),
                attributes=_create_attributes()
            )
            products.append(product)
    products = Product.objects.bulk_create(products)
    return products


def create_types(products=None):
    if products is None:
        products = Product.objects.all()
    elif not products:
        return []
    elif isinstance(products, (list, tuple)) and not products[0].pk:
        products_names = [product.name for product in products]
        products = Product.objects.filter(name__in=products_names)
    types = []
    for product in products:
        for j in range(randint(0, 7)):
            i_type = ProductType(
                product=product,
                units_count=_zero_or_in(1, 10),
                markup_percent=_zero_or_in(5, 20),
                properties=_create_properties(product)
            )
            types.append(i_type)
    return ProductType.objects.bulk_create(types)


def create_superuser():
    User.objects.create_superuser('a', 'aa@aa.com', 'a')


def fill(categories_count=5, sellers_count=10, customers_count=30):
    create_categories(categories_count)
    sellers = create_users(sellers_count)  # create sellers
    create_users(customers_count)  # create customers
    markets = create_markets(sellers)
    products = create_products(markets)
    create_types(products)


def get_natural_number(message, result_type=int):
    while True:
        num = input(message)
        if num.isdigit():
            return result_type(num)
        else:
            print(f'    {num} is not a natural number')


def fill_with_settings():
    filling_settings = {'categories_count': None, 'sellers_count': None, 'customers_count': None}
    for arg_name in filling_settings.keys():
        filling_settings[arg_name] = get_natural_number(f'Enter {arg_name.replace(" ", "")}: ')
    fill(**filling_settings)
