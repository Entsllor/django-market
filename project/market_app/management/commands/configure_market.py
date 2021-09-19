from django.core.management.base import BaseCommand
from django.core import management
from currencies.services import create_currencies_from_settings


class Command(BaseCommand):
    help = 'Configure the market app'

    def handle(self, *args, **options):
        management.call_command('makemigrations')
        management.call_command('migrate')
        management.call_command('create_currencies')
