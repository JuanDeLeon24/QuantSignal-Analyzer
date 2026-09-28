"""
Estadistica avanzada para evaluar estrategias y operaciones.

Todo trabaja sobre una serie de resultados en R (multiplos del riesgo),
que es la unidad comparable entre activos, tamanos y epocas.

Incluye:
  - Metricas clasicas: win rate, profit factor, expectativa, payoff, SQN.
  - Intervalos de confianza: Wilson (win rate) y bootstrap (expectativa, PF).
  - Significancia: t-test de expectativa > 0.
  - Probabilistic Sharpe Ratio y Deflated Sharpe Ratio (Bailey & Lopez de Prado).
  - Metricas de curva de capital: CAGR, Sharpe/Sortino anualizados, Calmar,
    Ulcer Index, recovery factor, tiempo bajo el agua.
  - Monte Carlo (remuestreo de la secuencia de operaciones): distribucion de
    retorno final y drawdown maximo, probabilidad de ruina.
  - Kelly (y fraccion recomendada).
  - Estabilidad walk-forward por segmentos de tiempo.
"""

import math

import numpy as np
import pandas as pd

try:
    from scipy import stats as _sps
except ImportError:  # pragma: no cover
    _sps = None

EULER_GAMMA = 0.5772156649


# =========================================================
# DISTRIBUCIONES (con fallback sin scipy)
# =========================================================

def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_ppf(p):
    if _sps is not None:
        return float(_sps.norm.ppf(p))
    # aproximacion de Acklam
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    q = min(max(p, 1e-12), 1 - 1e-12)
    if q < 0.02425:
        t = math.sqrt(-2 * math.log(q))
        return (((((c[0]*t+c[1])*t+c[2])*t+c[3])*t+c[4])*t+c[5]) / ((((d[0]*t+d[1])*t+d[2])*t+d[3])*t+1)
    if q > 1 - 0.02425:
        t = math.sqrt(-2 * math.log(1 - q))
        return -(((((c[0]*t+c[1])*t+c[2])*t+c[3])*t+c[4])*t+c[5]) / ((((d[0]*t+d[1])*t+d[2])*t+d[3])*t+1)
    t = q - 0.5
    r = t * t
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*t / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def _t_sf(t, df):
    if _sps is not None:
        return float(_sps.t.sf(t, df))
    return 1 - _norm_cdf(t)


# =========================================================
# METRICAS POR OPERACION
# =========================================================

def wilson_ci(wins, n, z=1.96):
    if n == 0:
        return (None, None)
    p = wins / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(max(0.0, centre - half) * 100, 2), round(min(1.0, centre + half) * 100, 2))


def _pf(r):
    g = r[r > 0].sum()
    l_ = -r[r <= 0].sum()
    return float(g / l_) if l_ > 0 else (float("inf") if g > 0 else 0.0)


def bootstrap_ci(r, func, n_boot=2000, alpha=0.05, seed=7):
    r = np.asarray(r, dtype=float)
    if len(r) < 5:
        return (None, None)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(r), size=(n_boot, len(r)))
    vals = np.array([func(r[i]) for i in idx])
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return (None, None)
    return (float(np.quantile(vals, alpha / 2)), float(np.quantile(vals, 1 - alpha / 2)))


def probabilistic_sharpe(r, sr_benchmark=0.0):
    """
    PSR: probabilidad de que el Sharpe (por operacion) verdadero supere
    `sr_benchmark`, corrigiendo por asimetria y curtosis de los resultados.
    """
    r = np.asarray(r, dtype=float)
    n = len(r)
    if n < 10 or r.std(ddof=1) == 0:
        return None
    sr = r.mean() / r.std(ddof=1)
    skew = float(pd.Series(r).skew())
    kurt = float(pd.Series(r).kurt()) + 3  # curtosis no-excesiva
    den = 1 - skew * sr + (kurt - 1) / 4 * sr * sr
    if den <= 0:
        return None
    z = (sr - sr_benchmark) * math.sqrt(n - 1) / math.sqrt(den)
    return _norm_cdf(z)


def expected_max_sharpe(n_trials, var_sharpe):
    """Sharpe maximo esperado solo por azar al probar `n_trials` variantes."""
    if n_trials <= 1 or var_sharpe <= 0:
        return 0.0
    return math.sqrt(var_sharpe) * (
        (1 - EULER_GAMMA) * _norm_ppf(1 - 1 / n_trials)
        + EULER_GAMMA * _norm_ppf(1 - 1 / (n_trials * math.e))
    )


def deflated_sharpe(r, n_trials, var_sharpe=None):
    """
    DSR: PSR usando como umbral el Sharpe maximo esperado por azar dado el
    numero de variantes probadas (estrategias x parametros). Corrige el
    sesgo de seleccion (quedarse con la mejor de muchas pruebas).
    """
    r = np.asarray(r, dtype=float)
    if len(r) < 10:
        return None
    if var_sharpe is None:
        var_sharpe = 1.0 / max(len(r) - 1, 1)
    return probabilistic_sharpe(r, expected_max_sharpe(n_trials, var_sharpe))


def kelly_fraction(win_rate, payoff):
    """f* = W - (1-W)/payoff  (en fraccion del capital por operacion)."""
    if payoff is None or payoff <= 0 or win_rate is None:
        return None
    return win_rate - (1 - win_rate) / payoff


def trade_stats(r, n_trials=1, ci=True):
    """
    Estadistica completa de una serie de resultados en R.
    `n_trials`: variantes probadas (para el Deflated Sharpe).
    """
    r = pd.Series(r, dtype=float).dropna()
    n = len(r)
    if n == 0:
        return {"trades": 0}

    wins = int((r > 0).sum())
    wr = wins / n
    avg_win = float(r[r > 0].mean()) if wins else 0.0
    avg_loss = float(-r[r <= 0].mean()) if n - wins else 0.0
    payoff = avg_win / avg_loss if avg_loss > 0 else None
    mean = float(r.mean())
    std = float(r.std(ddof=1)) if n > 1 else 0.0

    t_stat = mean / (std / math.sqrt(n)) if std > 0 and n > 1 else None
    p_value = _t_sf(t_stat, n - 1) if t_stat is not None else None

    streak = cur = 0
    for x in r:
        cur = cur + 1 if x <= 0 else 0
        streak = max(streak, cur)

    cum = r.cumsum()
    dd_r = float((cum.cummax().clip(lower=0) - cum).max())

    out = {
        "trades": n,
        "win_rate": round(wr * 100, 2),
        "expectancy_r": round(mean, 4),
        "std_r": round(std, 4),
        "total_r": round(float(r.sum()), 2),
        "profit_factor": round(_pf(r.values), 3) if np.isfinite(_pf(r.values)) else None,
        "avg_win_r": round(avg_win, 3),
        "avg_loss_r": round(avg_loss, 3),
        "payoff": round(payoff, 3) if payoff else None,
        "best_r": round(float(r.max()), 3),
        "worst_r": round(float(r.min()), 3),
        "max_loss_streak": streak,
        "max_drawdown_r": round(dd_r, 2),
        "sqn": round(math.sqrt(min(n, 100)) * mean / std, 3) if std > 0 else None,
        "sharpe_per_trade": round(mean / std, 4) if std > 0 else None,
        "skew": round(float(r.skew()), 3) if n > 2 else None,
        "t_stat": round(t_stat, 3) if t_stat is not None else None,
        "p_value": round(p_value, 4) if p_value is not None else None,
        "psr": round(probabilistic_sharpe(r.values), 4) if n >= 10 else None,
        "dsr": round(deflated_sharpe(r.values, n_trials), 4) if n >= 10 and n_trials > 1 else None,
        "n_trials": n_trials,
    }
    k = kelly_fraction(wr, payoff)
    out["kelly"] = round(k, 4) if k is not None else None

    if ci:
        out["win_rate_ci"] = wilson_ci(wins, n)
        lo, hi = bootstrap_ci(r.values, np.mean)
        out["expectancy_ci"] = (round(lo, 4), round(hi, 4)) if lo is not None else (None, None)
        lo, hi = bootstrap_ci(r.values, lambda x: min(_pf(x), 20.0))
        out["profit_factor_ci"] = (round(lo, 3), round(hi, 3)) if lo is not None else (None, None)

    out["verdict"] = edge_verdict(out)
    return out


def edge_verdict(s):
    """Lectura en lenguaje claro de si hay ventaja estadistica."""
    n = s.get("trades", 0)
    if n < 20:
        return "MUESTRA INSUFICIENTE"
    lo = (s.get("expectancy_ci") or (None, None))[0]
    p = s.get("p_value")
    if s["expectancy_r"] <= 0:
        return "SIN VENTAJA"
    if lo is not None and lo > 0 and p is not None and p < 0.05:
        if s.get("dsr") is not None and s["dsr"] < 0.9:
            return "VENTAJA PROBABLE (revisar sobreajuste)"
        return "VENTAJA SIGNIFICATIVA"
    if p is not None and p < 0.2:
        return "VENTAJA DEBIL / NO CONCLUYENTE"
    return "NO SIGNIFICATIVA"


# =========================================================
# CURVA DE CAPITAL
# =========================================================

def equity_from_trades(trades, risk_pct=1.0, initial=10000.0, compounding=True):
    """
    trades: DataFrame con exit_time y r (resultado neto en R).
    Devuelve Serie de equity indexada por exit_time.
    """
    if trades is None or len(trades) == 0:
        return pd.Series(dtype=float)
    t = trades.sort_values("exit_time")
    f = risk_pct / 100
    if compounding:
        eq = initial * np.cumprod(1 + f * t["r"].values)
    else:
        eq = initial * (1 + f * np.cumsum(t["r"].values))
    return pd.Series(eq, index=pd.to_datetime(t["exit_time"].values))


def equity_stats(equity, initial=10000.0, periods_per_year=252, calendar=None):
    """
    equity: Serie indexada por fecha (se lleva a frecuencia diaria).
    calendar: DatetimeIndex opcional (fechas de mercado) para el mark-to-market.
    """
    if equity is None or len(equity) == 0:
        return {}
    eq = equity.copy()
    eq = eq[~eq.index.duplicated(keep="last")]
    if calendar is not None and len(calendar):
        cal = pd.DatetimeIndex(calendar)
        daily = eq.reindex(cal.union(eq.index)).ffill().reindex(cal).fillna(initial)
    else:
        start = eq.index[0]
        daily = eq.resample("D").last().ffill()
        daily = pd.concat([pd.Series([initial], index=[start - pd.Timedelta(days=1)]), daily])

    rets = daily.pct_change().dropna()
    years = max((daily.index[-1] - daily.index[0]).days / 365.25, 1e-9)
    final = float(daily.iloc[-1])
    cagr = (final / initial) ** (1 / years) - 1 if final > 0 else -1.0

    peak = daily.cummax()
    dd = (daily / peak - 1)
    max_dd = float(-dd.min())
    ulcer = float(np.sqrt(np.mean((dd * 100) ** 2)))

    underwater = (dd < 0).astype(int)
    longest = cur = 0
    for u in underwater:
        cur = cur + 1 if u else 0
        longest = max(longest, cur)

    sd = rets.std(ddof=1)
    downside = rets[rets < 0].std(ddof=1)
    return {
        "final_equity": round(final, 2),
        "total_return_pct": round((final / initial - 1) * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "sharpe": round(float(rets.mean() / sd * math.sqrt(periods_per_year)), 3) if sd and sd > 0 else None,
        "sortino": round(float(rets.mean() / downside * math.sqrt(periods_per_year)), 3)
        if downside and downside > 0 else None,
        "max_drawdown_pct": round(max_dd * 100, 2),
        "calmar": round(cagr / max_dd, 3) if max_dd > 0 else None,
        "ulcer_index": round(ulcer, 3),
        "recovery_factor": round((final - initial) / (max_dd * initial), 3) if max_dd > 0 else None,
        "longest_underwater_days": int(longest),
        "years": round(years, 2),
    }


def drawdown_series(equity):
    peak = equity.cummax()
    return (equity / peak - 1) * 100


# =========================================================
# MONTE CARLO
# =========================================================

def monte_carlo(r, risk_pct=1.0, n_sims=5000, n_trades=None, ruin_dd=0.30, seed=11,
                initial=10000.0, block=1):
    """
    Remuestrea la secuencia de resultados (con reemplazo; `block`>1 conserva
    rachas) y simula curvas de capital con interes compuesto.

    Devuelve percentiles de retorno final y drawdown maximo, probabilidad de
    perder dinero, de ruina (DD >= ruin_dd) y bandas de la curva.
    """
    r = np.asarray(pd.Series(r).dropna(), dtype=float)
    n = len(r)
    if n < 5:
        return None
    n_trades = n_trades or n
    rng = np.random.default_rng(seed)
    f = risk_pct / 100

    if block <= 1:
        idx = rng.integers(0, n, size=(n_sims, n_trades))
    else:
        starts = rng.integers(0, n, size=(n_sims, math.ceil(n_trades / block)))
        idx = (starts[:, :, None] + np.arange(block)) % n
        idx = idx.reshape(n_sims, -1)[:, :n_trades]

    paths = initial * np.cumprod(1 + f * r[idx], axis=1)
    paths = np.clip(paths, 0, None)
    peaks = np.maximum.accumulate(np.concatenate([np.full((n_sims, 1), initial), paths], axis=1), axis=1)[:, 1:]
    max_dd = ((peaks - paths) / peaks).max(axis=1)
    final_ret = paths[:, -1] / initial - 1

    q = [5, 25, 50, 75, 95]
    bands = {p: np.percentile(paths, p, axis=0) for p in q}
    return {
        "n_sims": n_sims,
        "n_trades": n_trades,
        "risk_pct": risk_pct,
        "final_return_pct": {p: round(float(np.percentile(final_ret, p) * 100), 2) for p in q},
        "max_drawdown_pct": {p: round(float(np.percentile(max_dd, p) * 100), 2) for p in q},
        "prob_loss": round(float((final_ret < 0).mean()), 4),
        "prob_ruin": round(float((max_dd >= ruin_dd).mean()), 4),
        "ruin_threshold_pct": ruin_dd * 100,
        "bands": bands,
    }


def risk_of_ruin_table(r, risks=(0.5, 1, 2, 3, 5), n_sims=3000, ruin_dd=0.30):
    """Probabilidad de ruina y drawdown mediano segun el % arriesgado por operacion."""
    rows = []
    for rp in risks:
        mc = monte_carlo(r, risk_pct=rp, n_sims=n_sims, ruin_dd=ruin_dd)
        if mc is None:
            continue
        rows.append({
            "riesgo_%": rp,
            "retorno_mediano_%": mc["final_return_pct"][50],
            "retorno_p5_%": mc["final_return_pct"][5],
            "dd_mediano_%": mc["max_drawdown_pct"][50],
            "dd_p95_%": mc["max_drawdown_pct"][95],
            "prob_perdida": mc["prob_loss"],
            f"prob_DD>={int(ruin_dd * 100)}%": mc["prob_ruin"],
        })
    return pd.DataFrame(rows)


# =========================================================
# ESTABILIDAD
# =========================================================

def walk_forward_segments(trades, n_segments=5):
    """Divide las operaciones en segmentos consecutivos y mide cada uno."""
    if trades is None or len(trades) < n_segments * 3:
        return pd.DataFrame()
    t = trades.sort_values("entry_time").reset_index(drop=True)
    parts = np.array_split(np.arange(len(t)), n_segments)
    rows = []
    for k, idx in enumerate(parts, 1):
        seg = t.iloc[idx]
        r = seg["r"]
        rows.append({
            "segmento": k,
            "desde": pd.Timestamp(seg["entry_time"].iloc[0]).date(),
            "hasta": pd.Timestamp(seg["entry_time"].iloc[-1]).date(),
            "trades": len(seg),
            "win_rate": round(float((r > 0).mean() * 100), 1),
            "expectancy_r": round(float(r.mean()), 3),
            "profit_factor": round(min(_pf(r.values), 99), 2),
            "total_r": round(float(r.sum()), 2),
        })
    return pd.DataFrame(rows)


def stability_score(segments):
    """% de segmentos con expectativa positiva."""
    if segments is None or len(segments) == 0:
        return None
    return round(float((segments["expectancy_r"] > 0).mean() * 100), 1)


def regime_breakdown(trades, col):
    if trades is None or len(trades) == 0 or col not in trades.columns:
        return pd.DataFrame()
    g = trades.groupby(col)["r"]
    return pd.DataFrame({
        "trades": g.size(),
        "win_rate": (g.apply(lambda s: (s > 0).mean() * 100)).round(1),
        "expectancy_r": g.mean().round(3),
        "total_r": g.sum().round(2),
    }).reset_index()


def compare_to_benchmark(strategy_stats, benchmark_stats):
    keys = ["total_return_pct", "cagr_pct", "sharpe", "max_drawdown_pct", "calmar"]
    return {k: (strategy_stats.get(k), benchmark_stats.get(k)) for k in keys}
