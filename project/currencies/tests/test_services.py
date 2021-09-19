from decimal import Decimal

from django.conf import settings
from django.test import TestCase

from currencies.services import (
    get_currency_by_language, exchange_to, LOCAL_CURRENCIES, Currency, create_currencies_from_settings
)


def create_currency(code, sym, rate):
    obj = Currency.objects.create(code=code, sym=sym, rate=rate)
    return obj


class CurrencyTest(TestCase):
    def setUp(self) -> None:
        create_currencies_from_settings()

    def test_get_currency(self):
        for language_code, currency_code in LOCAL_CURRENCIES.items():
            currency = get_currency_by_language(language_code)
            self.assertEqual(currency.code, currency_code)

    def test_return_default_if_unexpected_language(self):
        self.assertNotEqual('TEST_CODE', settings.DEFAULT_CURRENCY)
        currency = get_currency_by_language('TEST_CODE')
        self.assertEqual(currency.code, settings.DEFAULT_CURRENCY)

    def test_exchange_to(self):
        amount_to_exchange = 100
        rate_of_test_currency = Decimal('2.33')
        create_currency(code='TEST', sym='T', rate=rate_of_test_currency)
        exchanged_amount = exchange_to('TEST', amount_to_exchange)
        self.assertEqual(exchanged_amount, rate_of_test_currency * amount_to_exchange)

    def test_pass_exchanging_if_codes_are_equal(self):
        amount_to_exchange = 100
        rate_of_test_currency = Decimal('2.33')
        create_currency(code='TEST', sym='T', rate=rate_of_test_currency)
        exchanged_amount = exchange_to('TEST', amount_to_exchange, 'TEST')
        self.assertEqual(exchanged_amount, amount_to_exchange)

    def test_exchange_to_default(self):
        amount_to_exchange = 100
        rate_of_test_currency = Decimal('5')
        create_currency(code='TEST', sym='T', rate=rate_of_test_currency)
        exchanged_amount = exchange_to(settings.DEFAULT_CURRENCY, amount_to_exchange, _from='TEST')
        self.assertEqual(exchanged_amount, 20)
