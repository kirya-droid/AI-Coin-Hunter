from loguru import logger
from .config import load_config
from .db.dao import DB
from .ingest.coingecko import fetch_top_markets
from .features.build import build_features
from .features.performance import evaluate_signal_performance
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

def _format_performance_update(update: dict) -> str:
    roi = update["roi_pct"]
    trend = "📈" if roi >= 0 else "📉"
    return (
        f"{trend} Итог по ${update['symbol']}: {roi:+.2f}% за {int(update['window_hours'])}ч\n"
        f"   Цена: {update['price_at_signal']:.6f} → {update['price_after']:.6f}"
    )


def pipeline_once():
    cfg = load_config()
    base_currency = (cfg.app.base_currency or "usd").lower()
    with DB() as db:
        run_id = db.run_start()
        try:
            # Pydantic model access must be via attributes, not dict subscripts
            top_cfg = cfg.sources.coingecko if cfg.sources and hasattr(cfg.sources, 'coingecko') else {}
            top_n = int((top_cfg or {}).get('top_n', 200))
            logger.info(f"Загружаем рынки с CoinGecko: top_n={top_n}")
            markets = fetch_top_markets(top_n=top_n, vs_currency=base_currency)
            previous_volumes = db.get_latest_volumes()
            feats = build_features(markets, previous_volume=previous_volumes)
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
                signal_id = db.insert_signal(
                    run_id,
                    it["asset_id"],
                    it["symbol"],
                    reason="rules",
                    summary=summary,
                    risk=risk,
                    score=score,
                )
                db.ensure_signal_performance(signal_id, it["asset_id"], it["symbol"], float(it.get("current_price", 0.0)))
                send_signal(format_card(it, summary))
            updates = evaluate_signal_performance(db, base_currency=base_currency)
            for update in updates:
                send_signal(_format_performance_update(update))
            db.run_finish(run_id, status="ok")
        except Exception as exc:
            logger.exception(exc)
            db.run_finish(run_id, status=f"error: {exc}")
            raise
