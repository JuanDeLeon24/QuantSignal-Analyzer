"""
Motor de analisis: ejecuta todo el pipeline tecnico para un activo y
devuelve UN diccionario con todo lo calculado (sin imprimir nada).

Ese diccionario es lo que se guarda en la bitacora como "senal", de modo
que cada recomendacion queda trazable: con que datos, con que version del
motor, con que features y con que resultado posterior.
"""

import hashlib
import uuid

import numpy as np

from config import settings
from config.settings import EMA_FAST, EMA_SLOW, INTERVAL, PERIOD

from data.cache import get_data as load_data

from indicators.ema import calculate_ema
from indicators.rsi import calculate_rsi
from indicators.macd import calculate_macd
from indicators.atr import calculate_atr
from indicators.adx import calculate_adx
from indicators.volume import calculate_volume_ma
from indicators.relative_volume import calculate_relative_volume
from indicators.volume_signal import get_volume_signal

from strategy.trend import get_trend
from strategy.score import calculate_score
from strategy.signal import get_signal
from strategy.confluence import analyze_confluence
from strategy.risk_manager import calculate_trade_plan
from strategy.position_size import calculate_position_size

from structure.swings import detect_swings
from structure.market_structure import get_market_structure
from structure.hh_hl import classify_structure
from structure.bos import detect_bos
from structure.choch import detect_choch
from structure.support import get_support
from structure.resistance import get_resistance
from structure.fibonacci import calculate_fibonacci
from structure.fibonacci_zone import get_fibonacci_zone
from structure.order_blocks import detect_order_blocks
from structure.liquidity import detect_liquidity
from structure.fvg import detect_fvg
from structure.premium_discount import get_pd_zone

from backtesting.simple_backtest import simple_backtest
from backtesting.advanced_backtest import advanced_backtest
from backtesting.advanced_backtest_v2 import advanced_backtest_v2

from ml.features import FEATURE_VERSION, add_indicators, feature_row


def probability_label(conf_score):

    if conf_score >= 90:
        return "EXTREMA"
    if conf_score >= 75:
        return "MUY ALTA"
    if conf_score >= 60:
        return "ALTA"
    if conf_score >= 40:
        return "MEDIA"
    return "BAJA"


def data_fingerprint(df, rows=300):
    tail = df[["Date", "Open", "High", "Low", "Close"]].tail(rows)
    return hashlib.sha256(tail.to_csv(index=False).encode()).hexdigest()[:16]


def run_analysis(symbol, df=None, period=None, interval=None,
                 account_size=None, risk_percent=None, research=True, scenarios=True,
                 legacy_backtests=False, pool_loader=None, pool=None):
    """
    research:    backtesting profesional (varias estrategias, Monte Carlo...)
    scenarios:   probabilidades del presente (analogos + Monte Carlo)
    pool_loader: funcion para cargar el universo de analogos (None = cache;
                 False = solo el propio activo)
    """
    from analytics.scenarios import build_scenarios
    from backtesting.engine import full_research, prepare
    from strategy.confluence_directional import analyze_confluence_directional

    period = period or settings.PERIOD
    interval = interval or settings.INTERVAL
    account_size = account_size or settings.ACCOUNT_SIZE
    risk_percent = risk_percent or settings.RISK_PERCENT

    if df is None:
        df = load_data(symbol, period, interval)

    incomplete = df.attrs.get("incomplete_dropped")
    raw = df.copy()

    # ===================== INDICADORES
    df = calculate_ema(df, EMA_FAST)
    df = calculate_ema(df, EMA_SLOW)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df = calculate_atr(df)
    df = calculate_adx(df)
    df = calculate_volume_ma(df)
    df = calculate_relative_volume(df)
    volume_signal = get_volume_signal(df)

    # ===================== ESTRUCTURA
    df = detect_swings(df)
    highs, lows = classify_structure(df)
    market_structure = get_market_structure(df)
    bos = detect_bos(df)
    choch = detect_choch(df)
    order_blocks = detect_order_blocks(df)
    liquidity = detect_liquidity(df)
    fvg = detect_fvg(df)
    pd_zone = get_pd_zone(df)
    support = get_support(df)
    resistance = get_resistance(df)

    # ===================== FIBONACCI
    fib_levels = calculate_fibonacci(df)
    last_close = float(df["Close"].iloc[-1])
    fib_zone = get_fibonacci_zone(last_close, fib_levels) if fib_levels else "SIN NIVELES"

    # ===================== SENAL
    trend = get_trend(df)
    score = calculate_score(df)
    signal = get_signal(score)

    conf_bull, factors_bull = analyze_confluence(trend, market_structure, bos, choch, fib_zone, df)

    directional = {}
    for d_ in ("LONG", "SHORT"):
        sc_, fav_, against_ = analyze_confluence_directional(
            d_, trend, market_structure, bos, choch, fib_zone, pd_zone, liquidity, df)
        directional[d_] = {"score": sc_, "factors": fav_, "against": against_}

    atr_now = float(df["ATR"].iloc[-1])
    trade_plan = calculate_trade_plan(last_close, support, resistance, atr_now, signal)

    plan_dir = trade_plan["direction"] if trade_plan["direction"] != "NONE" else trade_plan["plan_side"]
    conf_score = directional[plan_dir]["score"]
    factors = directional[plan_dir]["factors"]
    probability = probability_label(conf_score)

    position = calculate_position_size(account_size, risk_percent, trade_plan["entry"], trade_plan["stop"])

    # ===================== BACKTESTS
    backtest_v2 = advanced_backtest_v2(df)
    backtest_simple = simple_backtest(df) if legacy_backtests else None
    backtest_adv = advanced_backtest(df) if legacy_backtests else None

    prepared = prepare(raw)
    research_out = full_research(raw, symbol=symbol) if research else None

    # ===================== FEATURES IA
    ind = add_indicators(raw)
    features = feature_row(ind, len(ind) - 1)

    model_probs = {}
    try:
        from ml.model import predict_trade
        for d_ in ("LONG", "SHORT"):
            pred = predict_trade(features, d_)
            if pred is not None:
                model_probs[d_] = pred["p_win"]
    except Exception:  # noqa: BLE001 - la IA es opcional
        model_probs = {}
    model_probability = model_probs.get(trade_plan["direction"])

    # ===================== ESCENARIOS DEL PRESENTE
    scen = None
    if pool is None and scenarios and settings.ANALOG_SCOPE == "universo" and pool_loader is not False:
        try:
            from analytics.scenarios import get_universe_pool
            pool = get_universe_pool(loader=pool_loader)
        except Exception:  # noqa: BLE001 - sin datos del universo se usa solo el activo
            pool = None
    if scenarios:
        stop_atr = float(np.clip(trade_plan["risk"] / atr_now, 0.5, 6.0)) if atr_now > 0 else settings.SCENARIO_STOP_ATR
        scen = build_scenarios(
            prepared, stop_atr=stop_atr, targets_r=settings.SCENARIO_TARGETS,
            confluence={k: v["score"] for k, v in directional.items()},
            model_probs=model_probs or None, fee_pct=settings.FEE_PCT + settings.SLIPPAGE_PCT,
            pool=pool, symbol=symbol, k=settings.ANALOG_K if pool else 60,
        )

    recommendation = build_recommendation(trade_plan, scen, directional, research_out,
                                          account_size, risk_percent)

    ultimo = df.iloc[-1]

    return {
        "signal_id": str(uuid.uuid4()),
        "symbol": symbol,
        "interval": interval,
        "period": period,
        "candle_time": ultimo["Date"],
        "incomplete_dropped": incomplete,
        "df": df,
        "prepared": prepared,
        "trend": trend,
        "market_structure": market_structure,
        "hh_hl": (highs, lows),
        "bos": bos,
        "choch": choch,
        "order_blocks": order_blocks,
        "liquidity": liquidity,
        "fvg": fvg,
        "pd_zone": pd_zone,
        "support": float(support) if support is not None else None,
        "resistance": float(resistance) if resistance is not None else None,
        "fib_levels": fib_levels,
        "fib_zone": fib_zone,
        "volume_signal": volume_signal,
        "score": score,
        "signal": signal,
        "confluence_score": conf_score,
        "confluence_bullish_legacy": conf_bull,
        "directional": directional,
        "factors": factors,
        "probability": probability,
        "model_probability": model_probability,
        "model_probs": model_probs,
        "trade_plan": trade_plan,
        "position": position,
        "backtest_simple": backtest_simple,
        "backtest_advanced": backtest_adv,
        "backtest_v2": backtest_v2,
        "research": research_out,
        "scenarios": scen,
        "recommendation": recommendation,
        "backtest_summary": {
            k: backtest_v2[k] for k in (
                "trades", "win_rate", "profit_factor", "expectancy_r",
                "max_drawdown", "return_pct",
            )
        },
        "indicators": {
            "RSI": float(ultimo["RSI"]),
            "ADX": float(ultimo["ADX"]),
            "ATR": float(ultimo["ATR"]),
            "MACD": float(ultimo["MACD"]),
            "MACD_SIGNAL": float(ultimo["MACD_SIGNAL"]),
            "VOL_MA": float(ultimo["VOL_MA"]),
            "RVOL": float(ultimo["RVOL"]),
        },
        "context": {
            "trend": trend, "market_structure": market_structure, "bos": bos,
            "choch": choch, "liquidity": liquidity, "pd_zone": pd_zone,
            "fib_zone": fib_zone, "volume_signal": volume_signal,
            "fvg": fvg, "order_blocks": order_blocks,
            "support": float(support) if support is not None else None,
            "resistance": float(resistance) if resistance is not None else None,
            "confluence_long": directional["LONG"]["score"],
            "confluence_short": directional["SHORT"]["score"],
            "scenario": _scenario_context(scen),
            "recommendation": {k: v for k, v in recommendation.items() if k != "reasons"},
        },
        "features": features,
        "feature_version": FEATURE_VERSION,
        "engine_version": settings.ENGINE_VERSION,
        "data_hash": data_fingerprint(raw),
    }


def _scenario_context(scen):
    if not scen:
        return None
    out = {"best": scen["best_direction"], "n_analogs": scen["n_analogs"],
           "n_effective": scen.get("n_effective"), "n_assets": scen.get("n_assets"), "scope": scen.get("scope")}
    for d_, e in scen["directions"].items():
        out[d_] = {k: e[k] for k in ("score", "verdict", "ev_net_r", "p_main", "edge_main", "half_kelly_pct")}
    return out


def build_recommendation(plan, scen, directional, research, account_size, risk_percent):
    """
    Une la senal tecnica, los escenarios probabilisticos y el backtest en una
    recomendacion con su razonamiento.
    """
    reasons = []
    tech_dir = plan["direction"]

    if scen is None:
        action = tech_dir if tech_dir != "NONE" else "ESPERAR"
        return {"action": action, "direction": tech_dir, "score": None, "risk_pct": risk_percent,
                "reasons": ["Sin escenarios calculados"], "consistency": None}

    best = scen["directions"][tech_dir] if tech_dir in ("LONG", "SHORT") else scen["best"]
    other = scen["best"]

    if tech_dir == "NONE":
        reasons.append("La senal tecnica es ESPERAR (score intermedio).")
    if tech_dir in ("LONG", "SHORT") and other["direction"] != tech_dir and other["score"] > best["score"] + 10:
        reasons.append(f"Los escenarios favorecen {other['direction']} (score {other['score']}) "
                       f"frente a la senal tecnica {tech_dir} (score {best['score']}).")

    reasons.append(
        f"{best['direction']}: P(TP2 antes que stop) {best['p_main'] * 100:.1f}% vs "
        f"{(best['p_main'] - best['edge_main']) * 100:.1f}% por azar "
        f"(ventaja {best['edge_main'] * 100:+.1f} pp; {best['n_analogs']} casos parecidos de "
        f"{best.get('n_assets', 1)} activo(s), {best.get('n_effective', best['n_analogs'])} semanas independientes)."
    )
    reasons.append(f"Valor esperado neto de costes: {best['ev_net_r']:+.2f} R por operacion.")

    d = directional.get(best["direction"], {})
    if d.get("factors"):
        reasons.append("A favor: " + ", ".join(d["factors"][:4]) + ".")
    if d.get("against"):
        reasons.append("En contra: " + ", ".join(d["against"][:3]) + ".")

    if research:
        s = research["stats"]
        reasons.append(
            f"Mejor estrategia historica en este activo: {research['best'].name} "
            f"({s.get('trades', 0)} trades, expectativa {s.get('expectancy_r', 0):+.2f} R, "
            f"{s.get('verdict', '')})."
        )

    verdict_ = best["verdict"]
    if verdict_ == "FAVORABLE" and best["score"] >= 60:
        action = best["direction"]
    elif verdict_ in ("FAVORABLE", "MARGINAL"):
        action = f"{best['direction']} (tamano reducido)"
    else:
        action = "ESPERAR"

    if action == "ESPERAR":
        risk = 0.0
    else:
        risk = min(risk_percent, settings.MAX_RISK_PERCENT, max(best["half_kelly_pct"], 0.25))
        if "reducido" in action:
            risk = round(risk / 2, 2)

    consistency = None
    if tech_dir in ("LONG", "SHORT"):
        consistency = "ALINEADA" if other["direction"] == tech_dir else "EN CONFLICTO"

    return {
        "action": action,
        "direction": best["direction"],
        "score": best["score"],
        "verdict": verdict_,
        "risk_pct": round(risk, 2),
        "risk_amount": round(account_size * risk / 100, 2),
        "ev_net_r": best["ev_net_r"],
        "p_tp2": best["p_main"],
        "consistency": consistency,
        "reasons": reasons,
    }
