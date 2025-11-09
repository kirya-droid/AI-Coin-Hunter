from __future__ import annotations
from pydantic import BaseModel
from typing import Optional
import yaml, os

class RulesCfg(BaseModel):
    min_price_change_24h_pct: float = 15
    min_volume_change_24h_pct: float = 200
    min_rvol: float = 3
    min_market_cap_usd: float = 5_000_000

class AnomalyCfg(BaseModel):
    mode: str = "rules"
    rules: RulesCfg = RulesCfg()

class NotifyTelegramCfg(BaseModel):
    enabled: bool = True

class NotifyCfg(BaseModel):
    telegram: NotifyTelegramCfg = NotifyTelegramCfg()

class SourcesCfg(BaseModel):
    coingecko: dict
    news: dict

class AppCfg(BaseModel):
    base_currency: str = "USDT"
    network_timeout_s: int = 20

class ScheduleCfg(BaseModel):
    interval_minutes: int = 30

class Cfg(BaseModel):
    app: AppCfg
    sources: SourcesCfg
    anomaly: AnomalyCfg
    notify: NotifyCfg
    schedule: ScheduleCfg

_def_path = os.environ.get("CONFIG_PATH", "config.yaml")

def load_config(path: str | None = None) -> Cfg:
    with open(path or _def_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return Cfg(**raw)
