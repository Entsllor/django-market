import json
import logging
from decimal import Decimal

import requests
from django.conf import settings

logger = logging.getLogger('debug')

DEFAULT_CURRENCY = settings.DEFAULT_CURRENCY
SITE_URL = f'https://cdn.jsdelivr.net/gh/fawazahmed0/currency-api@1/latest/currencies/{DEFAULT_CURRENCY.lower()}.json'

language_currency = {
    'en-us': 'USD',
    'ru': 'RUB'
}


class Currency:
    def __init__(self, code: str, sym: str, rate: Decimal = None):
        self.code: str = code
        self.sym: str = sym
        self._rate: Decimal = rate

    @property
    def rate(self) -> Decimal:
        return self._rate

    @rate.setter
    def rate(self, value) -> None:
        self._rate = Decimal(value)

    def __str__(self):
        return self.code


currencies = {
    'USD': Currency(code='USD', sym='$', rate=Decimal('1')),
    'RUB': Currency(code='RUB', sym='₽')
}


def get_rates(*codes: str) -> dict:
    """Change this code if need to connect another currency API"""
    if not codes:
        codes = settings.EXTRA_CURRENCIES
    result = {}
    response = requests.get(SITE_URL)
    response_currencies = json.loads(response.text).get(DEFAULT_CURRENCY.lower())
    for currency_code in codes:
        rate = response_currencies.get(currency_code.lower())
        if rate:
            result[currency_code.upper()] = rate
        else:
            logger.warning(f"Failed to get currency rate: {currency_code}")
    return result


def update_currencies(*codes: str) -> None:
    if not codes:
        codes = settings.EXTRA_CURRENCIES
    rates = get_rates(*codes)
    for code in codes:
        code = code.upper()
        currency_to_update = currencies.get(code)
        if currency_to_update:
            currency_to_update.rate = rates[code]
            logger.info(f"The currency rate has been updated: {code}")
        else:
            logger.warning(f"The site doesn't support this currency: {code}")


update_currencies(*currencies.keys())


def get_currency(language_str: str):
    currency_code = language_currency.get(language_str.lower(), DEFAULT_CURRENCY)
    return currencies[currency_code]


def exchange_to(currency_code, amount, _from=DEFAULT_CURRENCY):
    if isinstance(amount, str):
        amount = Decimal(amount)
    if currency_code == _from:
        return amount
    exchange_rate = currencies[currency_code].rate / currencies[_from].rate
    exchanged_amount = (amount * exchange_rate).quantize(Decimal('1.00'))
    return exchanged_amount
