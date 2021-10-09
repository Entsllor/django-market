from decimal import Decimal
from typing import NamedTuple

from django.conf import settings

from .models import Currency, get_rates

DEFAULT_CURRENCY_CODE = settings.DEFAULT_CURRENCY_CODE
CURRENCY_CHOICES = []
LOCAL_CURRENCIES = settings.LOCAL_CURRENCIES


class LightWeightCurrency(NamedTuple):
    code: str
    sym: str
    rate: int


DEFAULT_CURRENCY = LightWeightCurrency(
    code=settings.DEFAULT_CURRENCY_CODE,
    sym=settings.CURRENCIES_SYMBOLS.get(settings.DEFAULT_CURRENCY_CODE, '?'),
    rate=1
)


def get_currency_choices():
    if not CURRENCY_CHOICES:
        CURRENCY_CHOICES.extend(
            (currency.code, currency.sym) for currency in Currency.objects.filter(code__in=settings.CURRENCIES)
        )
        if not CURRENCY_CHOICES:
            return (DEFAULT_CURRENCY_CODE, settings.CURRENCIES_SYMBOLS[DEFAULT_CURRENCY_CODE]),
    return CURRENCY_CHOICES


def create_currencies_from_settings():
    rates = get_rates(*settings.CURRENCIES)
    for currency_code in settings.CURRENCIES:
        Currency.objects.update_or_create(
            code=currency_code,
            sym=settings.CURRENCIES_SYMBOLS.get(currency_code, '?'),
            rate=rates[currency_code]
        )


def get_currency_by_code(code: str):
    if code == settings.DEFAULT_CURRENCY_CODE:
        return DEFAULT_CURRENCY
    return Currency.objects.filter(code=code).first() or DEFAULT_CURRENCY


def get_currency_code_by_language(language_str: str):
    return LOCAL_CURRENCIES.get(language_str.lower(), DEFAULT_CURRENCY_CODE)


def get_currency_by_language(language_str: str):
    currency_code = get_currency_code_by_language(language_str)
    return get_currency_by_code(currency_code)


def update_rates(*codes):
    if not codes:
        codes = settings.EXTRA_CURRENCIES
    Currency.objects.update_rates(codes)


def _exchange(amount, exchange_rate):
    if not isinstance(amount, Decimal):
        amount = Decimal(amount)
    return (amount * exchange_rate).quantize(Decimal('1.00'))


def _get_exchange_rate(to_currency, from_currency=DEFAULT_CURRENCY_CODE):
    if to_currency.upper() == from_currency.upper():
        return 1
    currencies_set = Currency.objects.only('rate', 'code').filter(code__in=(to_currency, from_currency))
    to_currency_rate = currencies_set.get(code=to_currency).rate
    from_currency_rate = currencies_set.get(code=from_currency).rate
    return to_currency_rate / from_currency_rate


def exchange_to(currency_code, amount, _from=DEFAULT_CURRENCY_CODE):
    exchange_rate = _get_exchange_rate(currency_code, _from)
    exchanged_amount = _exchange(amount, exchange_rate)
    return exchanged_amount


def get_exchanger(to: str, _from: str = DEFAULT_CURRENCY_CODE, by_language=False):
    if by_language:
        to = get_currency_code_by_language(to)
        if _from != DEFAULT_CURRENCY_CODE:
            _from = get_currency_code_by_language(_from)
    exchange_rate = _get_exchange_rate(to, _from)

    def exchanger(amount):
        return _exchange(amount, exchange_rate)

    return exchanger
