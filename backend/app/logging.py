import sys

from loguru import logger as _logger

from app.config import settings


_logger.remove()
_logger.add(
    sys.stderr,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level=settings.LOG_LEVEL,
)


def get_logger(name: str):
    return _logger.bind(name=name)
