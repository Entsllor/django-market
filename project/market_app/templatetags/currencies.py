from django import template
from ..currencies import get_currency, exchange_to
register = template.Library()


@register.filter
def currency_l10n(money_in_default_currency, language):
    currency = get_currency(language)
    exchanged_amount = exchange_to(currency.code, money_in_default_currency)
    return f'{exchanged_amount}{currency.sym}'
