from django.core import management
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Configure the market app'

    def handle(self, *args, **options):
        management.call_command('makemigrations')
        management.call_command('migrate')
        management.call_command('create_currencies')
        management.call_command('compilemessages')
