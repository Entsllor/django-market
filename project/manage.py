#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import sys

from project.settings.base_settings import env


def main():
    """Run administrative tasks."""
    env('DJANGO_SETTINGS_MODULE')
    if '--settings' not in ' '.join(sys.argv) and 'test' in sys.argv:
        # if you need to run tests with another module add '--settings SETTINGS_MODULE_NAME' argument
        sys.argv.append(f"--settings={'project.settings.testing'}")
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
