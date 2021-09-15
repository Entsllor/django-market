import logging

from django import template

from currencies.services import _exchange

register = template.Library()

logger = logging.getLogger('console')


@register.simple_tag(takes_context=True)
def to_local_currency(context, amount):
    if not amount:
        amount = 0
    currency = context.get("LOCAL_CURRENCY")
    exchanged_amount = _exchange(amount, currency.rate)
    return f'{exchanged_amount}{currency.sym}'
