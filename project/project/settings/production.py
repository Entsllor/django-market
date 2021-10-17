from .base_settings import *
import os

DEBUG = False


try:
    SECRET_KEY = os.environ['SECRET_KEY']
except KeyError:
    raise KeyError('SECRET_KEY is not in environmental variables. Set SECRET_KEY to run server.')

try:
    ALLOWED_HOSTS = os.environ['DJANGO_ALLOWED_HOSTS'].split()
except KeyError:
    raise KeyError('DJANGO_ALLOWED_HOSTS is not in environmental variables. Set DJANGO_ALLOWED_HOSTS to run server.')


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
