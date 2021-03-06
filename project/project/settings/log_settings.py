from pathlib import Path
from environ import Env

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = Env()
env.read_env(BASE_DIR / '.env', overwrite=True)
LOG_LEVEL = env("DJANGO_LOG_LEVEL", default="INFO")
LOG_DIR = Path(env("DJANGO_LOG_DIR", default='log'))
if LOG_DIR.is_absolute():
    LOG_DIR = BASE_DIR / LOG_DIR
if not LOG_DIR.exists():
    LOG_DIR.mkdir(parents=True)


LOGGING_SETTINGS = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module}: {message}',
            'style': '{',
        },
        'transaction': {
            'format': '{levelname} {asctime}: {message}',
            'style': '{',
        },
        'sql_query': {
            'format': '\n{levelname} {asctime} QUERY:\n{message}\n',
            'style': '{'
        }
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
        'money_transactions': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': LOG_DIR / 'transactions.log',
            'formatter': 'transaction'
        },
        'debug': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
        'sql_query_handler': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'sql_query'
        }
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': True,
        },
        'market_app.services': {
            'handlers': ['money_transactions'],
            'level': LOG_LEVEL,
            'propagate': True

        },
        'django.db.backends': {
            'level': LOG_LEVEL,
            'handlers': ['sql_query_handler'],
            'propagate': True
        },
    }
}
