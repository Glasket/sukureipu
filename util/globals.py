from pathlib import Path
import logging

CACHE = Path('~/.cache/sukureipu').expanduser()
CACHE.mkdir(parents=True, exist_ok=True)
LOGGER = logging.getLogger(__name__)
