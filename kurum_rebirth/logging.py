import logging
from logging import LogRecord
from logging.config import dictConfig

import PySimpleGUI as sg

logger = logging.getLogger(__name__)

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
        },
        'cprint': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'kurum_rebirth.logging.CPrintHandler',
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['default', 'cprint'],
            'level': 'WARNING',
            'propagate': False
        },
        'kurum_rebirth': {
            'handlers': ['default', 'cprint'],
            'level': 'INFO',
            'propagate': False
        },
        '__main__': {
            'handlers': ['default', 'cprint'],
            'level': 'INFO',
            'propagate': False
        },
    }
}


def init_logging():
    dictConfig(LOGGING_CONFIG)
    logger.info("Initialized Logging.")


class CPrintHandler(logging.Handler):
    def emit(self, record: LogRecord) -> None:
        sg.cprint(self.formatter.format(record))
