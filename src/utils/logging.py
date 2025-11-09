from loguru import logger
import sys

def setup_logging():
    logger.remove()
    logger.add(sys.stdout, level="INFO", enqueue=True, colorize=True,
               format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>")
    return logger
