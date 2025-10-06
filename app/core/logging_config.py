import logging, sys
from .config import get_settings

LEVEL_MAP = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL,
}

_configured = False

def configure_logging():
    global _configured
    if _configured:
        return
    settings = get_settings()
    level = LEVEL_MAP.get(settings.log_level.lower(), logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    _configured = True
