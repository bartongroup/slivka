import logging
import os

import pybioas

_logger = None

def get_logger():
    global _logger
    if _logger is None:
        _logger = logging.getLogger(__name__)
        _logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "Command %(levelname)s: %(message)s"
        )

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        _logger.addHandler(stream_handler)

        file_handler = logging.FileHandler(
            os.path.join(pybioas.settings.BASE_DIR, "Command.log"))
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        _logger.addHandler(file_handler)
    return _logger
