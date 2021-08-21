from django.core.management.base import BaseCommand

from currencies.services import create_currencies_from_settings


class Command(BaseCommand):
    help = 'Create currencies'

    def handle(self, *args, **options):
        create_currencies_from_settings()
