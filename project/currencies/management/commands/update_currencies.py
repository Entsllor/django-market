from django.conf import settings
from django.core.management.base import BaseCommand

from currencies.services import update_rates

DEFAULT_CURRENCY = settings.DEFAULT_CURRENCY
SITE_URL = f'https://cdn.jsdelivr.net/gh/fawazahmed0/currency-api@1/latest/currencies/{DEFAULT_CURRENCY.lower()}.json'


class Command(BaseCommand):
    help = 'Update currencies rates'

    def add_arguments(self, parser):
        parser.add_argument('currencies', nargs='*', help='currencies', type=str.lower)

    def handle(self, *args, **options):
        currencies_to_update = options.get('currencies')
        update_rates(*currencies_to_update)
