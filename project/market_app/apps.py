from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class MarketAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'market_app'
    verbose_name = _('Shopping')

    def ready(self):
        from . import signals
