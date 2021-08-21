from decimal import Decimal

from django.conf import settings

from .models import Currency, get_rates

DEFAULT_CURRENCY = settings.DEFAULT_CURRENCY

ASSOCIATED_CURRENCY = {
    'en-us': 'USD',
    'ru': 'RUB'
}


def get_currency_choices():
    return [(currency.code, currency.sym) for currency in Currency.objects.filter(code__in=settings.CURRENCIES)]


def create_currencies_from_settings():
    rates = get_rates(*settings.CURRENCIES)
    for currency_code in settings.CURRENCIES:
        Currency.objects.update_or_create(
            code=currency_code,
            sym=settings.CURRENCIES_SYMBOLS.get(currency_code, '?'),
            rate=rates[currency_code]
        )


def get_currency_by_code(code: str):
    print('Try to get code')
    return Currency.objects.get(code=code)


def get_currency_by_language(language_str: str):
    currency_code = ASSOCIATED_CURRENCY.get(language_str.lower(), DEFAULT_CURRENCY)
    return get_currency_by_code(currency_code)


def update_rates(*codes):
    if not codes:
        codes = settings.EXTRA_CURRENCIES
    Currency.objects.update_rates(codes)


def _exchange(amount, exchange_rate):
    return (amount * exchange_rate).quantize(Decimal('1.00'))


def _get_exchange_rate(to_currency, from_currency=DEFAULT_CURRENCY):
    currencies_set = Currency.objects.only('rate', 'code').filter(code__in=(to_currency, from_currency))
    to_currency_rate = currencies_set.get(code=to_currency).rate
    from_currency_rate = currencies_set.get(code=from_currency).rate
    return to_currency_rate / from_currency_rate


def exchange_to(currency_code, amount, _from=DEFAULT_CURRENCY):
    if isinstance(amount, str):
        amount = Decimal(amount)
    if currency_code == _from:
        return amount
    exchange_rate = _get_exchange_rate(currency_code, _from)
    exchanged_amount = _exchange(amount, exchange_rate)
    return exchanged_amount
