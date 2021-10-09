import json
import logging

import requests
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger('debug')

DEFAULT_CURRENCY = settings.DEFAULT_CURRENCY_CODE
SITE_URL = f'https://cdn.jsdelivr.net/gh/fawazahmed0/currency-api@1/latest/currencies/{DEFAULT_CURRENCY.lower()}.json'


def get_rates(*codes: str) -> dict:
    """Change this code if need to connect another currency API"""
    if not codes:
        codes = settings.CURRENCIES
    result = {}
    response = requests.get(SITE_URL)
    response_currencies = json.loads(response.text).get(DEFAULT_CURRENCY.lower())
    for currency_code in codes:
        rate = response_currencies.get(currency_code.lower())
        if rate:
            result[currency_code.upper()] = rate
        else:
            logger.warning(f"Failed to get currency rate: {currency_code}")
    if not result[DEFAULT_CURRENCY] == 1:
        raise AssertionError(
            'Side API returned invalid values. '
            f'Expected default currency rate equals 1 but not {result[DEFAULT_CURRENCY]}')
    return result


class CurrencyManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()

    def update_rates(self, codes: str) -> None:
        if not codes:
            currencies_to_update = self.filter(code__in=codes)
        else:
            currencies_to_update = self.all()
        rates = get_rates()
        for cur_to_update in currencies_to_update:
            cur_to_update.rate = rates[cur_to_update.code]
        currencies_to_update.bulk_update(currencies_to_update, fields=['rate'])


class Currency(models.Model):
    code = models.CharField(verbose_name=_('currency code'), max_length=5, primary_key=True)
    sym = models.CharField(verbose_name=_('currency symbol'), max_length=1)
    rate = models.DecimalField(verbose_name=_('exchange rate'), max_digits=5, decimal_places=2)

    def __str__(self) -> str:
        return self.code

    class Meta:
        verbose_name = _('currency')
        verbose_name_plural = _('currencies')

    objects = CurrencyManager()
