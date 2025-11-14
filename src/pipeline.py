import datetime as dt

from loguru import logger
from .config import load_config, CryptoPanicCfg
from .db.dao import DB
from .ingest.coingecko import fetch_top_markets
from .ingest.news import fetch_asset_news
from .features.build import build_features
from .features.performance import evaluate_signal_performance
from .detect.rules import detect_by_rules
from .llm.explain import explain_signal
from .models.apply import load_model_bundle, score_candidates
from .notify.telegram_bot import send_signal

def format_card(
    item: dict,
    summary: str,
    *,
    ml_score: float | None = None,
    ml_threshold: float | None = None,
    news_brief: str | None = None,
) -> str:
    lines = [
        f"<b>🔥 Аномалия:</b> ${item['symbol'].upper()} — {item['name']}",
        (
            "📈 ΔP 24ч: <b>{p24:.1f}%</b> | ΔP 7д: <b>{p7:.1f}%</b> | ΔP 30д: <b>{p30:.1f}%</b>"
        ).format(
            p24=item.get("price_change_percentage_24h", 0.0),
            p7=item.get("price_change_percentage_7d", 0.0),
            p30=item.get("price_change_percentage_30d", 0.0),
        ),
        (
            "📊 ΔV≈ <b>{dvol:.0f}%</b> | rVOL: <b>{rvol:.2f}</b> | Диапазон 24ч: <b>{rng:.1f}%</b>"
        ).format(
            dvol=item.get("volume_change_24h_pct", 0.0),
            rvol=item.get("rvol", 0.0),
            rng=item.get("intraday_range_pct", 0.0),
        ),
        (
            "💰 Цена: {price} | Cap: {cap:,} | Волат.: {vol:.1f}%"
        ).format(
            price=item.get("current_price"),
            cap=int(item.get("market_cap", 0) or 0),
            vol=item.get("volatility_annualized_pct", 0.0),
        ),
    ]
    if ml_score is not None:
        if ml_threshold is not None:
            status = "✅" if ml_score >= ml_threshold else "⚠️"
            lines.append(f"🤖 ML-score: {ml_score:.2f} (порог {ml_threshold:.2f}) {status}")
        else:
            lines.append(f"🤖 ML-score: {ml_score:.2f}")
    if news_brief:
        lines.append(f"📰 {news_brief}")
    lines.append(f"🧠 {summary}")
    return "\n".join(lines)

def _format_performance_update(update: dict) -> str:
    roi = update["roi_pct"]
    trend = "📈" if roi >= 0 else "📉"
    created_at = update.get("signal_created_at")
    created_fmt = created_at.strftime("%Y-%m-%d %H:%M UTC") if created_at else "—"
    risk = update.get("risk_note") or "—"
    score = update.get("score")
    score_txt = f"{score:.2f}" if isinstance(score, (int, float)) else "—"
    lines = [
        f"{trend} Итог по ${update['symbol']}: {roi:+.2f}% за {int(update['window_hours'])}ч",
        f"   Цена: {update['price_at_signal']:.6f} → {update['price_after']:.6f}",
        f"   🧠 Score: {score_txt} | Риск: {risk}",
        f"   🕒 Сигнал: {created_fmt}",
    ]
    summary = update.get("llm_summary")
    if summary:
        lines.append(f"   📝 {summary}")
    return "\n".join(lines)


def _format_digest(summary: dict, *, days: int) -> str:
    total = summary.get("total", 0)
    winners = summary.get("winners", 0) or 0
    losers = summary.get("losers", 0) or 0
    win_rate = (winners / total * 100) if total else 0.0
    avg_roi = summary.get("avg_roi") or 0.0
    max_roi = summary.get("max_roi") or 0.0
    min_roi = summary.get("min_roi") or 0.0
    return (
        f"📊 Итоги за {days}д: {total} сигналов (✅ {winners} / ❌ {losers})\n"
        f"   Win rate: {win_rate:.1f}% | Avg ROI: {avg_roi:+.2f}%\n"
        f"   Max ROI: {max_roi:+.2f}% | Min ROI: {min_roi:+.2f}%"
    )


def _resolve_news_cfg(cfg) -> tuple[CryptoPanicCfg | None, str]:
    news_cfg = getattr(cfg.sources, "cryptopanic", None)
    legacy_news = getattr(cfg.sources, "news", None)
    reason: str

    if news_cfg is None:
        reason = "раздел sources.cryptopanic отсутствует"
    elif getattr(news_cfg, "enabled", False):
        reason = "sources.cryptopanic.enabled=true"
    else:
        reason = "sources.cryptopanic.enabled=false"

    if isinstance(legacy_news, dict) and legacy_news.get("enabled"):
        merged = {}
        if news_cfg:
            base_cfg = (
                news_cfg.model_dump()
                if hasattr(news_cfg, "model_dump")
                else news_cfg.dict()
            )
            merged.update(base_cfg)
        merged.update(
            {
                key: legacy_news.get(key)
                for key in ("auth_token", "min_votes", "max_headlines", "lookback_hours")
                if key in legacy_news
            }
        )
        merged["enabled"] = True
        news_cfg = CryptoPanicCfg(**merged)
        reason = "legacy sources.news.enabled=true → CryptoPanic включён"

    return news_cfg, reason


def pipeline_once():
    cfg = load_config()
    base_currency = (cfg.app.base_currency or "usd").lower()
    performance_window = cfg.anomaly.rules.performance_window_hours
    llm_cfg = getattr(cfg, "llm", None)
    ml_bundle = load_model_bundle(cfg.ml.model_path) if getattr(cfg, "ml", None) and cfg.ml.enabled else None
    with DB() as db:
        run_id = db.run_start()
        try:
            # Pydantic model access must be via attributes, not dict subscripts
            top_cfg = cfg.sources.coingecko if cfg.sources and hasattr(cfg.sources, 'coingecko') else {}
            top_n = int((top_cfg or {}).get('top_n', 200))
            logger.info(f"Загружаем рынки с CoinGecko: top_n={top_n}")
            markets = fetch_top_markets(top_n=top_n, vs_currency=base_currency)
            previous_snapshots = db.get_latest_snapshot_stats()
            price_history = db.get_price_history(window_hours=max(72, performance_window * 3))
            snapshot_time = dt.datetime.utcnow()
            feats = build_features(
                markets,
                previous_snapshots=previous_snapshots,
                price_history=price_history,
                current_time=snapshot_time,
            )
            news_cfg, news_reason = _resolve_news_cfg(cfg)
            logger.info(f"CryptoPanic: {news_reason}")
            if news_cfg is not None:
                enabled_flag = "yes" if getattr(news_cfg, "enabled", False) else "no"
                lookback_hours = getattr(news_cfg, "lookback_hours", "?")
                max_headlines = getattr(news_cfg, "max_headlines", "?")
                min_votes = getattr(news_cfg, "min_votes", "?")
                logger.info(
                    "CryptoPanic параметры: enabled=%s | lookback=%sh | max_headlines=%s | min_votes=%s",
                    enabled_flag,
                    lookback_hours,
                    max_headlines,
                    min_votes,
                )
            news_map: dict[str, dict] = {}
            news_fallback: str | None = None
            if news_cfg and news_cfg.enabled:
                symbols = feats["symbol"].tolist()
                unique_symbol_count = len({sym.upper() for sym in symbols if sym})
                lookback = getattr(news_cfg, "lookback_hours", None)
                max_headlines = getattr(news_cfg, "max_headlines", None)
                logger.info(
                    f"CryptoPanic: запрашиваем новости (тикеров={unique_symbol_count}, "
                    f"lookback={lookback}h, max_headlines={max_headlines})"
                )
                news_map = fetch_asset_news(symbols, news_cfg)
                total_headlines = sum(len(v.get("headlines", [])) for v in news_map.values())
                symbols_with_news = len([1 for v in news_map.values() if v.get("headlines")])
                logger.info(
                    f"CryptoPanic: получено новостей для {symbols_with_news}/{unique_symbol_count} "
                    f"тикеров, заголовков={total_headlines}"
                )
                if total_headlines == 0:
                    lookback_text = f"{lookback}ч" if lookback else "указанный период"
                    logger.warning(
                        "CryptoPanic: заголовки не найдены за %s — проверьте фильтры или наличие новостей",
                        lookback_text,
                    )
                feats = feats.copy()
                feats["symbol_upper"] = feats["symbol"].str.upper()
                feats["news_count"] = feats["symbol_upper"].map(lambda sym: len(news_map.get(sym, {}).get("headlines", [])))
                feats["news_sentiment"] = feats["symbol_upper"].map(lambda sym: news_map.get(sym, {}).get("sentiment_score", 0.0))
                feats.drop(columns=["symbol_upper"], inplace=True)
                if total_headlines == 0:
                    if lookback:
                        news_fallback = f"релевантных новостей не найдено за последние {lookback}ч"
                    else:
                        news_fallback = "релевантных новостей не найдено за указанный период"
            else:
                if news_cfg and not news_cfg.enabled:
                    logger.info("CryptoPanic новости отключены конфигурацией")
                else:
                    logger.info("CryptoPanic конфигурация отсутствует — новости пропущены")
                feats = feats.copy()
                feats["news_count"] = 0
                feats["news_sentiment"] = 0.0
            candidates = detect_by_rules(
                feats,
                min_price_change_24h_pct=cfg.anomaly.rules.min_price_change_24h_pct,
                min_volume_change_24h_pct=cfg.anomaly.rules.min_volume_change_24h_pct,
                min_rvol=cfg.anomaly.rules.min_rvol,
                min_market_cap_usd=cfg.anomaly.rules.min_market_cap_usd,
            )
            db.insert_snapshots(run_id, feats.to_dict(orient="records"), created_at=snapshot_time)
            logger.info(f"Найдено кандидатов: {len(candidates)}")
            ml_scores: list[float] = []
            if ml_bundle and candidates:
                try:
                    ml_scores = score_candidates(
                        ml_bundle,
                        candidates,
                        feature_override=getattr(cfg.ml, "feature_overrides", None),
                    )
                except Exception as ml_exc:
                    logger.warning("ML scoring failed: {}", ml_exc)
                    ml_scores = []
            for idx, it in enumerate(candidates):
                summary, risk, score = explain_signal(
                    it,
                    model=getattr(llm_cfg, "model", None) if llm_cfg else None,
                    temperature=getattr(llm_cfg, "temperature", None) if llm_cfg else None,
                    max_tokens=getattr(llm_cfg, "max_tokens", None) if llm_cfg else None,
                    window_hours=performance_window,
                    news_brief=(
                        news_map.get(it["symbol"].upper(), {}).get("headline_summary")
                        if news_map and news_map.get(it["symbol"].upper(), {}).get("headline_summary")
                        else news_fallback
                    ),
                )
                news_info = news_map.get(it["symbol"].upper()) if news_map else None
                if news_info:
                    it["news_count"] = len(news_info.get("headlines", []))
                    it["news_sentiment"] = news_info.get("sentiment_score", 0.0)
                signal_id = db.insert_signal(
                    run_id,
                    it["asset_id"],
                    it["symbol"],
                    reason="rules",
                    summary=summary,
                    risk=risk,
                    score=score,
                )
                db.ensure_signal_performance(
                    signal_id,
                    it["asset_id"],
                    it["symbol"],
                    float(it.get("current_price", 0.0)),
                    window_hours=performance_window,
                )
                ml_score = ml_scores[idx] if idx < len(ml_scores) else None
                news_brief = None
                if news_map:
                    summary_text = news_map.get(it["symbol"].upper(), {}).get("headline_summary")
                    news_brief = summary_text if summary_text else news_fallback
                elif news_fallback:
                    news_brief = news_fallback
                ml_threshold = None
                if ml_bundle:
                    ml_threshold = getattr(cfg.ml, "threshold", None) or ml_bundle.threshold
                send_signal(
                    format_card(
                        it,
                        summary,
                        ml_score=ml_score,
                        ml_threshold=ml_threshold,
                        news_brief=news_brief,
                    )
                )
            updates = evaluate_signal_performance(db, base_currency=base_currency)
            for update in updates:
                send_signal(_format_performance_update(update))
            perf_summary = db.get_performance_summary(days=7)
            if perf_summary:
                send_signal(_format_digest(perf_summary, days=7))
            db.run_finish(run_id, status="ok")
        except Exception as exc:
            logger.exception(exc)
            db.run_finish(run_id, status=f"error: {exc}")
            raise
