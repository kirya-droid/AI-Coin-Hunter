
from apscheduler.schedulers.blocking import BlockingScheduler
from .pipeline import pipeline_once
from .config import load_config
from .utils.logging import setup_logging
from .utils.env import load_env
import os

def _log_env():
    from loguru import logger
    token = bool(os.getenv("TELEGRAM_BOT_TOKEN"))
    chat  = os.getenv("TELEGRAM_CHAT_ID")
    logger.info(f"Telegram configured: token={'yes' if token else 'no'}, chat_id={chat if chat else 'None'}")

def run_once():
    setup_logging()
    load_env()
    _log_env()
    pipeline_once()

def run_interval():
    setup_logging()
    load_env()
    _log_env()
    cfg = load_config()
    minutes = cfg.schedule.interval_minutes
    from loguru import logger
    logger.info(f"Starting scheduler with interval {minutes} min (UTC)")
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(pipeline_once, "interval", minutes=minutes, max_instances=1, coalesce=True, misfire_grace_time=60)
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
