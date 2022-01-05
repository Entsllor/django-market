#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import sys

from project.settings.base_settings import env

PRODUCTION = 'project.settings.production'
DEVELOPMENT = 'project.settings.development'
TESTING = 'project.settings.testing'


def main():
    """Run administrative tasks."""
    if '--settings' not in ' '.join(sys.argv):
        settings_module = env('DJANGO_SETTINGS_MODULE', default='').lower()
        # if you need to run tests with another module add '--settings SETTINGS_MODULE_NAME' argument
        if 'test' in sys.argv:
            settings_module = TESTING
        # aliases
        elif settings_module in ('prod', 'production'):
            settings_module = PRODUCTION
        elif settings_module in ('dev', 'development'):
            settings_module = DEVELOPMENT
        elif settings_module in ('test', 'testing'):
            settings_module = TESTING
        sys.argv.append(f"--settings={settings_module}")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
