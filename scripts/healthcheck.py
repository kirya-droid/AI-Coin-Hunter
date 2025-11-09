#!/usr/bin/env python

"""Run lightweight diagnostics to ensure external dependencies are reachable."""

import argparse
import os
import socket
import sys
import time
from contextlib import closing

import requests
from loguru import logger

from src.config import load_config


def _check_tcp(host: str, port: int, timeout: float = 5.0) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None, help="Path to config file")
    args = parser.parse_args()

    cfg = load_config(args.config)
    logger.info(
        "Loaded config: base currency {}, top_n={}",
        cfg.app.base_currency,
        (cfg.sources.coingecko or {}).get("top_n"),
    )

    if not _check_tcp("api.coingecko.com", 443):
        logger.warning("TCP connectivity to api.coingecko.com:443 failed")
    try:
        resp = requests.get("https://api.coingecko.com/api/v3/ping", timeout=10)
        resp.raise_for_status()
        logger.success("CoinGecko reachable: {}", resp.json())
    except Exception as exc:
        logger.error("CoinGecko API check failed: {}", exc)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        logger.info("Telegram credentials detected")
    else:
        logger.warning("Telegram credentials missing; notifications will be disabled")

    if cfg.sources.cryptopanic.enabled:
        logger.info("Checking CryptoPanic availability")
        try:
            resp = requests.get("https://cryptopanic.com/api/v1/posts/", params={"public": "true"}, timeout=10)
            resp.raise_for_status()
            logger.success("CryptoPanic reachable")
        except Exception as exc:
            logger.error("CryptoPanic check failed: {}", exc)

    model_path = cfg.ml.model_path if cfg.ml.enabled else None
    if model_path:
        if os.path.exists(model_path):
            logger.success("ML model found at {}", model_path)
        else:
            logger.warning("Configured ML model path {} does not exist", model_path)

    # Basic clock drift detection using monotonic timer
    start = time.perf_counter()
    time.sleep(0.1)
    elapsed = time.perf_counter() - start
    if elapsed <= 0:
        logger.warning("System clock unstable (elapsed={:.6f})", elapsed)
    else:
        logger.info("Monotonic timer healthy (elapsed={:.6f})", elapsed)


if __name__ == "__main__":
    sys.exit(main())
