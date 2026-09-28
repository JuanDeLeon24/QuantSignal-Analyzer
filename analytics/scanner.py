"""
Escaner de oportunidades: analiza la watchlist completa y la ordena por
Decision Score / valor esperado, e incluye comparacion entre activos
(fuerza relativa, volatilidad, correlaciones).
"""

import numpy as np
import pandas as pd

from config import settings


def scan(symbols=None, loader=None, with_backtest=True, log=print, progress=None):
    """
    Analiza todos los activos. Con loader=None usa la cache local y descarga
    en lote lo que falte; el universo de analogos se prepara una sola vez.
    """
    from analytics.scenarios import get_universe_pool
    from core.analyzer import run_analysis

    symbols = list(symbols or settings.WATCHLIST)
    rows, analyses, closes = [], {}, {}

    if loader is None:
        from data.cache import load_many
        frames, errors = load_many(symbols, progress=progress, log=log)
    else:
        frames, errors = {}, {}
        for s in symbols:
            try:
                frames[s] = loader(s, settings.PERIOD, settings.INTERVAL)
            except Exception as e:  # noqa: BLE001
                errors[s] = str(e)[:120]

    pool = None
    if settings.ANALOG_SCOPE == "universo":
        pool = get_universe_pool(symbols, loader=loader)   # se prepara una sola vez para todo el escaneo

    todo = [s for s in symbols if s in frames]
    for k, sym in enumerate(todo, 1):
        if progress:
            progress(k - 1, len(todo), f"analizando {sym}")
        try:
            a = run_analysis(sym, df=frames[sym], research=with_backtest,
                             pool=pool, pool_loader=False if pool is None else None)
        except Exception as e:  # noqa: BLE001
            errors[sym] = str(e)[:160]
            log(f"  {sym}: error {e}")
            continue
        analyses[sym] = a
        closes[sym] = a["prepared"].set_index("Date")["Close"]
        rows.append(_row(sym, a))
    if progress:
        progress(len(todo), len(todo), "listo")

    table = pd.DataFrame(rows)
    if len(table):
        table = table.sort_values("score", ascending=False).reset_index(drop=True)
        table.insert(0, "rank", range(1, len(table) + 1))
    by_class = pd.DataFrame()
    if len(table):
        g = table.groupby("clase")
        by_class = pd.DataFrame({
            "activos": g.size(),
            "score_medio": g["score"].mean().round(1),
            "favorables": g["veredicto"].apply(lambda s: int((s == "FAVORABLE").sum())),
            "long": g["direccion"].apply(lambda s: int((s == "LONG").sum())),
            "short": g["direccion"].apply(lambda s: int((s == "SHORT").sum())),
            "ev_medio_r": g["ev_neto_r"].mean().round(3),
        }).reset_index().sort_values("score_medio", ascending=False)
    return {"table": table, "analyses": analyses, "comparison": compare_assets(closes),
            "errors": errors, "by_class": by_class}


def _row(sym, a):
    rec = a["recommendation"]
    sc = a["scenarios"]
    best = sc["directions"][rec["direction"]] if sc else {}
    d = a["prepared"]
    c = d["Close"]
    r = a.get("research")
    return {
        "activo": sym,
        "nombre": settings.NAMES.get(sym, ""),
        "clase": settings.asset_class(sym),
        "precio": float(c.iloc[-1]),
        "accion": rec["action"],
        "direccion": rec["direction"],
        "score": rec.get("score"),
        "veredicto": rec.get("verdict"),
        "p_tp2": rec.get("p_tp2"),
        "ventaja_pp": best.get("edge_main", 0) * 100 if best else None,
        "ev_neto_r": rec.get("ev_net_r"),
        "riesgo_%": rec.get("risk_pct"),
        "senal_tecnica": a["signal"],
        "conf_long": a["directional"]["LONG"]["score"],
        "conf_short": a["directional"]["SHORT"]["score"],
        "ret_20v_%": float((c.iloc[-1] / c.iloc[-21] - 1) * 100) if len(c) > 21 else None,
        "atr_%": float(d["f_atr"].iloc[-1] / c.iloc[-1] * 100),
        "mejor_estrategia": r["best"].name if r else None,
        "exp_estrategia_r": r["stats"].get("expectancy_r") if r else None,
        "veredicto_backtest": r["stats"].get("verdict") if r else None,
    }


def compare_assets(closes, lookback=250):
    """Fuerza relativa, volatilidad, drawdown y correlaciones entre activos."""
    if not closes:
        return {}
    px = pd.DataFrame(closes).sort_index()
    # Alinear calendarios distintos (cripto 7 dias vs acciones 5): por fecha diaria
    px.index = pd.to_datetime(px.index).normalize()
    px = px.groupby(level=0).last()
    # correlacion solo en fechas comunes (sin rellenar)
    rets = px.pct_change(fill_method=None).tail(lookback)
    stats = []
    for s in px.columns:
        p = px[s].dropna().tail(lookback + 1)
        r = p.pct_change().dropna()
        if len(p) < 30:
            continue
        ann = 365 if s.endswith("-USD") else 252
        stats.append({
            "activo": s,
            "ret_20_%": (p.iloc[-1] / p.iloc[-21] - 1) * 100 if len(p) > 21 else np.nan,
            "ret_60_%": (p.iloc[-1] / p.iloc[-61] - 1) * 100 if len(p) > 61 else np.nan,
            "ret_periodo_%": (p.iloc[-1] / p.iloc[0] - 1) * 100,
            "vol_anual_%": r.std() * np.sqrt(ann) * 100,
            "sharpe_periodo": (r.mean() / r.std() * np.sqrt(ann)) if r.std() > 0 else np.nan,
            "max_dd_%": float(((p / p.cummax()) - 1).min() * 100),
        })
    st_df = pd.DataFrame(stats)
    if len(st_df):
        st_df["rank_fuerza"] = st_df["ret_60_%"].rank(ascending=False, method="first").astype("Int64")
        st_df = st_df.sort_values("rank_fuerza")
    corr = rets.corr(min_periods=30) if rets.shape[1] > 1 else pd.DataFrame()
    return {"stats": st_df, "corr": corr, "prices": px.ffill().tail(lookback + 1)}
