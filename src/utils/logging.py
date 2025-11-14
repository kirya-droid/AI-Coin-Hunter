from __future__ import annotations

from pathlib import Path
from loguru import logger
import sys

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "ai_coin_hunter.log"


def setup_logging():
    """Configure Loguru sinks for console and rotating file outputs."""

    logger.remove()

    logger.add(
        sys.stdout,
        level="INFO",
        enqueue=True,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
        ),
    )

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Fall back to console-only logging if we cannot create the directory.
        logger.warning("Не удалось создать каталог логов '{}'", LOG_DIR)
    else:
        logger.add(
            LOG_FILE,
            level="INFO",
            enqueue=True,
            encoding="utf-8",
            rotation="5 MB",
            retention=5,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function} - {message}"
            ),
        )
        logger.info("Журналирование включено: {}", LOG_FILE.resolve())

    return logger
