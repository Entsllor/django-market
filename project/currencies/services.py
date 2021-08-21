from decimal import Decimal

from django.conf import settings

from .models import Currency, get_rates

DEFAULT_CURRENCY = settings.DEFAULT_CURRENCY

language_currency = {
    'en-us': 'USD',
    'ru': 'RUB'
}


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


def get_currency_by_language(language_str: str):
    currency_code = language_currency.get(language_str.lower(), DEFAULT_CURRENCY)
    return get_currency_by_code(currency_code)


def update_rates(*codes):
    if not codes:
        codes = settings.EXTRA_CURRENCIES
    Currency.objects.update_rates(codes)


def exchange_to(currency_code, amount, _from=DEFAULT_CURRENCY):
    if isinstance(amount, str):
        amount = Decimal(amount)
    if currency_code == _from:
        return amount
    exchange_rate = get_currency_by_code(currency_code).rate / get_currency_by_code(_from).rate
    exchanged_amount = (amount * exchange_rate).quantize(Decimal('1.00'))
    return exchanged_amount
