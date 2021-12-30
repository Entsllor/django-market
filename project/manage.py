#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import sys

from project.settings.base_settings import env


def main():
    """Run administrative tasks."""
    if '--settings' not in ' '.join(sys.argv):
        env('DJANGO_SETTINGS_MODULE', default='project.settings.production')
    if 'test' in sys.argv and '--settings' not in ' '.join(sys.argv):
        sys.argv.append('--settings=project.settings.testing')
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
