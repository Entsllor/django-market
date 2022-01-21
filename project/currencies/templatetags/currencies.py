import logging

from django import template

from currencies.models import Currency
from currencies.services import _exchange, DEFAULT_CURRENCY

register = template.Library()

logger = logging.getLogger('console')


@register.simple_tag(takes_context=True)
def to_local_currency(context, amount):
    # WARNING! Use returned value only for displaying not as an operand
    if not amount:
        amount = 0
    currency = context.get("LOCAL_CURRENCY")
    try:
        exchanged_amount = _exchange(amount, currency.rate)
    except Currency.DoesNotExist:
        return f"{amount}{DEFAULT_CURRENCY.sym}"
    return f'{exchanged_amount}{currency.sym}'
