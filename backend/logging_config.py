from __future__ import annotations

import logging

from .config import settings


def configure_logging() -> None:
    """Configure app-wide logging.

    Keeps things simple and works well with uvicorn's default logging.
    """
    level_name = (settings.LOG_LEVEL or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Keep third-party noise down unless the user explicitly asked for it.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
