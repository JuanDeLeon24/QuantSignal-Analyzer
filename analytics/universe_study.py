"""
Estudio multi-activo: corre las 6 estrategias sobre TODO el universo
(50 activos por defecto) y responde:

  - Que estrategia funciona de forma consistente en muchos activos
    (y no solo en uno por casualidad)?
  - En que clase de activo (cripto, acciones, forex...) funciona cada una?
  - Cual es la estadistica agregada con miles de operaciones (IC95, p-valor,
    Deflated Sharpe corrigiendo por las 6 x 50 pruebas)?

Guarda todas las operaciones simuladas (casos de estudio) en CSV.
"""

from datetime import datetime

import numpy as np
import pandas as pd

from analytics import stats as S
from backtesting.engine import STRATEGIES, buy_and_hold, config_for, prepare, run_backtest
from config import settings


def universe_study(symbols=None, loader=None, keys=None, progress=None, log=print, save=True):
    symbols = list(symbols or settings.WATCHLIST)
    keys = keys or list(STRATEGIES)

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

    all_trades, per_asset, bench_rows = [], [], []
    n = len(frames)
    for k, (sym, df) in enumerate(frames.items(), 1):
        if progress:
            progress(k - 1, n, f"backtest {sym}")
        if df is None or len(df) < 300:
            errors[sym] = "historico insuficiente"
            continue
        d = prepare(df)
        cls = settings.asset_class(sym)
        _, b = buy_and_hold(d)
        bench_rows.append({"activo": sym, "clase": cls, "bh_cagr_%": b.get("cagr_pct"),
                           "bh_sharpe": b.get("sharpe"), "bh_max_dd_%": b.get("max_drawdown_pct")})
        for key in keys:
            res = run_backtest(d, STRATEGIES[key]["fn"](d), config_for(key), STRATEGIES[key]["label"])
            t = res.trades
            if len(t):
                t = t.assign(estrategia=key, activo=sym, clase=cls)
                all_trades.append(t)
            r = t["r"] if len(t) else pd.Series(dtype=float)
            per_asset.append({
                "estrategia": key, "activo": sym, "clase": cls, "trades": len(r),
                "expectancy_r": float(r.mean()) if len(r) else np.nan,
                "win_rate": float((r > 0).mean() * 100) if len(r) else np.nan,
                "total_r": float(r.sum()) if len(r) else 0.0,
            })
    if progress:
        progress(n, n, "listo")

    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    pa = pd.DataFrame(per_asset)
    n_trials = len(keys) * max(1, len(frames))

    summary = []
    for key in keys:
        t = trades[trades["estrategia"] == key] if len(trades) else pd.DataFrame()
        s = S.trade_stats(t["r"] if len(t) else [], n_trials=n_trials)
        a = pa[(pa["estrategia"] == key) & (pa["trades"] >= 5)]
        summary.append({
            "estrategia": STRATEGIES[key]["label"], "clave": key,
            "trades": s.get("trades", 0),
            "activos_con_ops": int((pa[(pa["estrategia"] == key)]["trades"] > 0).sum()),
            "win_rate": s.get("win_rate"),
            "expectancy_r": s.get("expectancy_r"),
            "exp_ci_low": (s.get("expectancy_ci") or (None, None))[0],
            "exp_ci_high": (s.get("expectancy_ci") or (None, None))[1],
            "profit_factor": s.get("profit_factor"),
            "p_value": s.get("p_value"),
            "dsr": s.get("dsr"),
            "sqn": s.get("sqn"),
            "consistencia_%": round(float((a["expectancy_r"] > 0).mean() * 100), 1) if len(a) else None,
            "mediana_activo_r": round(float(a["expectancy_r"].median()), 3) if len(a) else None,
            "veredicto": s.get("verdict"),
        })
    summary = pd.DataFrame(summary).sort_values("expectancy_r", ascending=False, na_position="last").reset_index(drop=True)

    by_class = pd.DataFrame()
    if len(trades):
        g = trades.groupby(["estrategia", "clase"])["r"]
        by_class = pd.DataFrame({
            "trades": g.size(),
            "win_rate": g.apply(lambda s: (s > 0).mean() * 100).round(1),
            "expectancy_r": g.mean().round(3),
            "p_value": g.apply(lambda s: S.trade_stats(s, ci=False).get("p_value")),
        }).reset_index()
        by_class["estrategia"] = by_class["estrategia"].map(lambda k: STRATEGIES[k]["label"])

    matrix = pa.pivot_table(index="estrategia", columns="activo", values="expectancy_r") if len(pa) else pd.DataFrame()
    if len(matrix):
        matrix = matrix.reindex(columns=[s for s in symbols if s in matrix.columns])

    by_year = pd.DataFrame()
    if len(trades):
        tt = trades.assign(anio=pd.to_datetime(trades["entry_time"]).dt.year)
        by_year = tt.pivot_table(index="estrategia", columns="anio", values="r", aggfunc="mean").round(3)
        by_year.index = [STRATEGIES[k]["label"] for k in by_year.index]

    out = {
        "symbols": list(frames),
        "errors": errors,
        "summary": summary,
        "per_asset": pa,
        "by_class": by_class,
        "matrix": matrix,
        "by_year": by_year,
        "benchmark": pd.DataFrame(bench_rows),
        "trades": trades,
        "n_trials": n_trials,
    }
    if len(summary) and len(trades):
        best = summary.iloc[0]["clave"]
        bt = trades[trades["estrategia"] == best]
        out["best_key"] = best
        out["best_mc"] = S.monte_carlo(bt.sort_values("entry_time")["r"], risk_pct=settings.RISK_PERCENT / 5,
                                       n_sims=3000)
    if save and len(trades):
        settings.ensure_dirs()
        p = settings.DATASETS_DIR / f"estudio_universo_{datetime.now():%Y%m%d_%H%M}.csv"
        trades.to_csv(p, index=False)
        out["trades_path"] = p
    return out
