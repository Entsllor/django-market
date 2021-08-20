import copy
from decimal import Decimal

from django.test import SimpleTestCase

from ..currencies import (
    get_currency, exchange_to, DEFAULT_CURRENCY, currencies, language_currency, Currency
)


class CurrencyTest(SimpleTestCase):
    def setUp(self) -> None:
        self.currencies_backup = copy.deepcopy(currencies)

    def test_get_currency(self):
        for language_code, currency_code in language_currency.items():
            currency = get_currency(language_code)
            self.assertEqual(currency.code, currency_code)

    def test_return_default_if_unexpected_language(self):
        self.assertNotEqual('TEST_CODE', DEFAULT_CURRENCY)
        currency = get_currency('TEST_CODE')
        self.assertEqual(currency.code, DEFAULT_CURRENCY)

    def test_exchange_to(self):
        amount_to_exchange = 100
        rate_of_test_currency = Decimal('2.33')
        currencies['test'] = Currency(code='TEST', sym='T', rate=rate_of_test_currency)
        exchanged_amount = exchange_to('test', amount_to_exchange)
        self.assertEqual(exchanged_amount, rate_of_test_currency * amount_to_exchange)

    def test_pass_exchanging_if_codes_are_equal(self):
        amount_to_exchange = 100
        rate_of_test_currency = Decimal('2.33')
        currencies['test'] = Currency(code='TEST', sym='T', rate=rate_of_test_currency)
        exchanged_amount = exchange_to('test', amount_to_exchange, 'test')
        self.assertEqual(exchanged_amount, amount_to_exchange)

    def test_exchange_to_default(self):
        amount_to_exchange = 100
        rate_of_test_currency = Decimal('5')
        currencies['test'] = Currency(code='TEST', sym='T', rate=rate_of_test_currency)
        exchanged_amount = exchange_to(DEFAULT_CURRENCY, amount_to_exchange, _from='test')
        self.assertEqual(exchanged_amount, 20)

    def tearDown(self) -> None:
        currencies = self.currencies_backup
