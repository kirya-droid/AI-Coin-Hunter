from loguru import logger
from .config import load_config
from .db.dao import DB
from .ingest.coingecko import fetch_top_markets
from .features.build import build_features
from .detect.rules import detect_by_rules
from .llm.explain import explain_signal
from .notify.telegram_bot import send_signal

def format_card(item: dict, summary: str) -> str:
    return (
        f"<b>🔥 Аномалия:</b> ${item['symbol'].upper()} — {item['name']}\n"
        f"📈 ΔP 24ч: <b>{item['price_change_percentage_24h']:.1f}%</b> | ΔV≈ <b>{item['volume_change_24h_pct']:.0f}%</b> | rVOL: <b>{item['rvol']:.2f}</b>\n"
        f"💰 Цена: {item['current_price']} | Cap: {int(item['market_cap']):,}\n"
        f"🧠 {summary}"
    )

def pipeline_once():
    cfg = load_config()
    db = DB()
    run_id = db.run_start()
    try:
        # Pydantic model access must be via attributes, not dict subscripts
        top_cfg = cfg.sources.coingecko if cfg.sources and hasattr(cfg.sources, 'coingecko') else {}
        top_n = int((top_cfg or {}).get('top_n', 200))
        logger.info(f"Загружаем рынки с CoinGecko: top_n={top_n}")
        markets = fetch_top_markets(top_n=top_n, vs_currency="usd")
        feats = build_features(markets)
        candidates = detect_by_rules(
            feats,
            min_price_change_24h_pct=cfg.anomaly.rules.min_price_change_24h_pct,
            min_volume_change_24h_pct=cfg.anomaly.rules.min_volume_change_24h_pct,
            min_rvol=cfg.anomaly.rules.min_rvol,
            min_market_cap_usd=cfg.anomaly.rules.min_market_cap_usd,
        )
        db.insert_snapshots(run_id, feats.to_dict(orient="records"))
        logger.info(f"Найдено кандидатов: {len(candidates)}")
        for it in candidates:
            summary, risk, score = explain_signal(it)
            db.insert_signal(run_id, it["asset_id"], it["symbol"], reason="rules", summary=summary, risk=risk, score=score)
            send_signal(format_card(it, summary))
        db.run_finish(run_id, status="ok")
    except Exception as e:
        logger.exception(e)
        db.run_finish(run_id, status=f"error: {e}")
        raise
