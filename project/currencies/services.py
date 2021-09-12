from decimal import Decimal

from django.conf import settings

from .models import Currency, get_rates

DEFAULT_CURRENCY = settings.DEFAULT_CURRENCY
CURRENCY_CHOICES = [(currency.code, currency.sym) for currency in Currency.objects.filter(code__in=settings.CURRENCIES)]
ASSOCIATED_CURRENCY = {
    'en-us': 'USD',
    'ru': 'RUB'
}


def get_currency_choices():
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
    return Currency.objects.get(code=code)


def get_currency_code_by_language(language_str: str):
    return ASSOCIATED_CURRENCY.get(language_str.lower(), DEFAULT_CURRENCY)


def get_currency_by_language(language_str: str):
    currency_code = get_currency_code_by_language(language_str)
    return get_currency_by_code(currency_code)


def update_rates(*codes):
    if not codes:
        codes = settings.EXTRA_CURRENCIES
    Currency.objects.update_rates(codes)


def _exchange(amount, exchange_rate):
    if isinstance(amount, str):
        amount = Decimal(amount)
    if exchange_rate == 1:
        return amount
    return (amount * exchange_rate).quantize(Decimal('1.00'))


def _get_exchange_rate(to_currency, from_currency=DEFAULT_CURRENCY):
    currencies_set = Currency.objects.only('rate', 'code').filter(code__in=(to_currency, from_currency))
    to_currency_rate = currencies_set.get(code=to_currency).rate
    from_currency_rate = currencies_set.get(code=from_currency).rate
    return to_currency_rate / from_currency_rate


def exchange_to(currency_code, amount, _from=DEFAULT_CURRENCY):
    exchange_rate = _get_exchange_rate(currency_code, _from)
    exchanged_amount = _exchange(amount, exchange_rate)
    return exchanged_amount


def get_exchanger(to: str, _from: str = DEFAULT_CURRENCY, by_language=False):
    if by_language:
        to = get_currency_code_by_language(to)
        if _from != DEFAULT_CURRENCY:
            _from = get_currency_code_by_language(_from)
    exchange_rate = _get_exchange_rate(to, _from)

    def exchanger(amount):
        return _exchange(amount, exchange_rate)

    return exchanger
