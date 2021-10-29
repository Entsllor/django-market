import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = BASE_DIR
TRANSACTION_LOG_PATH = BASE_DIR.joinpath('log/transactions.log')
if not TRANSACTION_LOG_PATH.parent.exists():
    TRANSACTION_LOG_PATH.parent.mkdir()

LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO")

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
            'filename': TRANSACTION_LOG_PATH,
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
