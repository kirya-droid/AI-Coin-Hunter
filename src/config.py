from __future__ import annotations
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List
from loguru import logger
import yaml, os

class RulesCfg(BaseModel):
    min_price_change_24h_pct: float = 15
    min_volume_change_24h_pct: float = 200
    min_rvol: float = 3
    min_market_cap_usd: float = 5_000_000
    performance_window_hours: int = 24

class AnomalyCfg(BaseModel):
    mode: str = "rules"
    rules: RulesCfg = RulesCfg()

class NotifyTelegramCfg(BaseModel):
    enabled: bool = True

class NotifyCfg(BaseModel):
    telegram: NotifyTelegramCfg = NotifyTelegramCfg()

class LLMCfg(BaseModel):
    model: str = "gpt-5-nano"
    temperature: float = 0.35
    max_tokens: int = 220

class CryptoPanicCfg(BaseModel):
    enabled: bool = False
    auth_token: Optional[str] = None
    min_votes: int = 0
    max_headlines: int = 3
    lookback_hours: int = 24


class SourcesCfg(BaseModel):
    coingecko: Optional[dict] = None
    news: Optional[dict] = None  # backward compatibility with legacy configs
    cryptopanic: CryptoPanicCfg = Field(default_factory=CryptoPanicCfg)

class AppCfg(BaseModel):
    base_currency: str = "USDT"
    network_timeout_s: int = 20

class ScheduleCfg(BaseModel):
    interval_minutes: int = 30

class MLCfg(BaseModel):
    enabled: bool = False
    model_path: Optional[str] = None
    threshold: float = 0.55
    feature_overrides: Optional[List[str]] = None

class Cfg(BaseModel):
    app: AppCfg
    sources: SourcesCfg
    anomaly: AnomalyCfg
    notify: NotifyCfg
    schedule: ScheduleCfg
    llm: LLMCfg = LLMCfg()
    ml: MLCfg = MLCfg()

_def_path = os.environ.get("CONFIG_PATH", "config.yaml")

def load_config(path: str | None = None) -> Cfg:
    cfg_path = Path(path or _def_path)
    with cfg_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    cfg = Cfg(**raw)
    try:
        logger.info("Загружен конфиг: {}", cfg_path.resolve())
    except Exception:
        # Logging should never break config loading; ignore resolution errors.
        logger.info("Загружен конфиг: {}", cfg_path)
    return cfg
