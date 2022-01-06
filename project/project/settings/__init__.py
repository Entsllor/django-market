# use project.settings instead of project.settings.<file_name>
import os

from .base_settings import env

SETTINGS_MODULES = {
    'PRODUCTION': 'project.settings.production',
    'DEVELOPMENT': 'project.settings.development',
    'TESTING': 'project.settings.testing'
}

SETTINGS_MODULE = env('DJANGO_SETTINGS_MODULE').lower()
os.environ['DJANGO_SETTINGS_MODULE'] = 'project.settings'

# aliases
if SETTINGS_MODULE in ('prod', 'production', SETTINGS_MODULES['PRODUCTION']):
    SETTINGS_MODULE = SETTINGS_MODULES['PRODUCTION']
    from .production import *
elif SETTINGS_MODULE in ('dev', 'development', SETTINGS_MODULES['DEVELOPMENT']):
    SETTINGS_MODULE = SETTINGS_MODULES['DEVELOPMENT']
    from .development import *
elif SETTINGS_MODULE in ('test', 'testing', SETTINGS_MODULES['TESTING']):
    SETTINGS_MODULE = SETTINGS_MODULES['TESTING']
    from .testing import *
