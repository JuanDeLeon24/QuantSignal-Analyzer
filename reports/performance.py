"""
Metricas de rendimiento sobre operaciones REALES de la bitacora
(no sobre el backtest).
"""

import json

import numpy as np
import pandas as pd


def _json_list(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return []
    if isinstance(v, list):
        return v
    try:
        x = json.loads(v)
        return x if isinstance(x, list) else []
    except (TypeError, ValueError):
        return []


def closed_trades(trades):
    if trades is None or len(trades) == 0:
        return pd.DataFrame()
    df = trades[trades["status"] == "CLOSED"].copy()
    if len(df) == 0:
        return df
    df["exit_time"] = pd.to_datetime(df["exit_time"])
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    return df.sort_values("exit_time").reset_index(drop=True)


def summary(trades, account_size=10000.0):
    """KPIs principales. `trades` = DataFrame de journal.list_trades()."""
    df = closed_trades(trades)
    n = len(df)
    if n == 0:
        return {"trades": 0}

    pnl = df["pnl"].fillna(0)
    r = df["r_multiple"].fillna(0)

    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]

    equity = account_size + pnl.cumsum()
    peak = equity.cummax()
    dd_pct = ((peak - equity) / peak * 100)

    cum_r = r.cumsum()
    dd_r = (cum_r.cummax() - cum_r)

    streak_w = streak_l = cur_w = cur_l = 0
    for x in pnl:
        if x > 0:
            cur_w += 1
            cur_l = 0
        else:
            cur_l += 1
            cur_w = 0
        streak_w, streak_l = max(streak_w, cur_w), max(streak_l, cur_l)

    sharpe = None
    if n >= 5 and r.std(ddof=1) > 0:
        # Sharpe por operacion (en R). No anualizado: frecuencia irregular.
        sharpe = round(float(r.mean() / r.std(ddof=1)), 3)

    return {
        "trades": n,
        "wins": int((pnl > 0).sum()),
        "losses": int((pnl <= 0).sum()),
        "win_rate": round(float((pnl > 0).mean() * 100), 2),
        "profit_factor": round(float(wins.sum() / abs(losses.sum())), 2) if losses.sum() != 0 else None,
        "total_pnl": round(float(pnl.sum()), 2),
        "total_r": round(float(r.sum()), 2),
        "expectancy_r": round(float(r.mean()), 3),
        "avg_win_r": round(float(r[r > 0].mean()), 3) if (r > 0).any() else None,
        "avg_loss_r": round(float(r[r <= 0].mean()), 3) if (r <= 0).any() else None,
        "best_r": round(float(r.max()), 2),
        "worst_r": round(float(r.min()), 2),
        "max_drawdown_pct": round(float(dd_pct.max()), 2),
        "max_drawdown_r": round(float(dd_r.max()), 2),
        "sharpe_per_trade": sharpe,
        "max_win_streak": streak_w,
        "max_loss_streak": streak_l,
        "avg_holding_hours": round(float(df["holding_hours"].mean()), 1) if df["holding_hours"].notna().any() else None,
        "plan_adherence_pct": round(float(df["followed_plan"].dropna().mean() * 100), 1)
        if df["followed_plan"].notna().any() else None,
        "fees": round(float(df["fees"].fillna(0).sum()), 2),
    }


def equity_series(trades, account_size=10000.0):
    df = closed_trades(trades)
    if len(df) == 0:
        return df
    out = df[["exit_time", "symbol", "source", "pnl", "r_multiple"]].copy()
    out["equity"] = account_size + out["pnl"].fillna(0).cumsum()
    out["cum_r"] = out["r_multiple"].fillna(0).cumsum()
    peak = out["equity"].cummax()
    out["drawdown_pct"] = (peak - out["equity"]) / peak * 100
    return out


def breakdown(trades, by):
    """Tabla de rendimiento agrupada (setup, symbol, source, emotion_entry...)."""
    df = closed_trades(trades)
    if len(df) == 0 or by not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df[by] = df[by].fillna("(sin dato)")
    g = df.groupby(by)
    res = pd.DataFrame({
        "trades": g.size(),
        "win_rate": g["pnl"].apply(lambda s: (s > 0).mean() * 100).round(1),
        "expectancy_r": g["r_multiple"].mean().round(3),
        "total_r": g["r_multiple"].sum().round(2),
        "total_pnl": g["pnl"].sum().round(2),
    })
    return res.sort_values("total_r", ascending=False).reset_index()


def mistakes_breakdown(trades):
    """Costo de cada error etiquetado (en R)."""
    df = closed_trades(trades)
    if len(df) == 0:
        return pd.DataFrame()
    rows = []
    for _, t in df.iterrows():
        for m in _json_list(t.get("mistakes")):
            rows.append({"mistake": m, "r": t["r_multiple"], "pnl": t["pnl"]})
    if not rows:
        return pd.DataFrame()
    x = pd.DataFrame(rows)
    return (
        x.groupby("mistake")
        .agg(veces=("r", "size"), total_r=("r", "sum"), expectancy_r=("r", "mean"))
        .round(3)
        .sort_values("total_r")
        .reset_index()
    )


def time_breakdown(trades, local_tz="America/Bogota"):
    df = closed_trades(trades)
    if len(df) == 0:
        return pd.DataFrame(), pd.DataFrame()
    local = pd.to_datetime(df["entry_time"]).dt.tz_localize("UTC").dt.tz_convert(local_tz)
    df = df.assign(weekday=local.dt.dayofweek, hour=local.dt.hour)
    dias = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    wd = df.groupby("weekday")["r_multiple"].agg(["size", "sum", "mean"]).reset_index()
    wd["weekday"] = wd["weekday"].map(lambda d: dias[int(d)])
    hr = df.groupby("hour")["r_multiple"].agg(["size", "sum", "mean"]).reset_index()
    return wd, hr


def signals_summary(signals):
    """Rendimiento de las senales del sistema (se hayan operado o no)."""
    if signals is None or len(signals) == 0:
        return pd.DataFrame()
    s = signals[signals["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])]
    if len(s) == 0:
        return pd.DataFrame()
    g = s.groupby("probability")
    res = pd.DataFrame({
        "senales": g.size(),
        "win_rate": g["outcome_r"].apply(lambda x: (x > 0).mean() * 100).round(1),
        "expectancy_r": g["outcome_r"].mean().round(3),
    }).reset_index()
    order = {"BAJA": 0, "MEDIA": 1, "ALTA": 2, "MUY ALTA": 3, "EXTREMA": 4}
    res["_o"] = res["probability"].map(order)
    return res.sort_values("_o").drop(columns="_o")


def system_vs_you(trades, signals):
    """
    Compara: senales del sistema (resultado teorico) vs tus operaciones
    vinculadas a esas senales (resultado real). Mide cuanto aportas o
    restas con tu ejecucion.
    """
    df = closed_trades(trades)
    if len(df) == 0 or signals is None or len(signals) == 0:
        return pd.DataFrame()
    linked = df[df["signal_id"].notna()]
    if len(linked) == 0:
        return pd.DataFrame()
    m = linked.merge(
        signals[["id", "outcome", "outcome_r"]],
        left_on="signal_id", right_on="id", suffixes=("", "_sig"),
    )
    m = m[m["outcome_r"].notna()]
    if len(m) == 0:
        return pd.DataFrame()
    m["diferencia_r"] = m["r_multiple"] - m["outcome_r"]
    return m[["id", "symbol", "direction", "r_multiple", "outcome", "outcome_r", "diferencia_r"]]
