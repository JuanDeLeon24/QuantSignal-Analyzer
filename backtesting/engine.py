"""
Motor de backtesting profesional de QuantSignal AI.

Diferencias con los backtests anteriores:
  - Senal al CIERRE de la vela i, entrada a la APERTURA de la vela i+1
    (no se opera con un precio que ya paso).
  - Comisiones y slippage en ambos lados, descontados en R.
  - Stop y objetivo por ATR; si en una vela se tocan ambos, cuenta el stop.
  - LONG y SHORT.
  - Registro de cada operacion con regimen de mercado, MAE/MFE y motivo de salida.
  - Varias estrategias comparables sobre los mismos datos + benchmark buy & hold.
  - Sensibilidad de parametros y estadistica avanzada (analytics.stats).
"""

from dataclasses import asdict, dataclass, replace

import numpy as np
import pandas as pd

from analytics import stats as st
from ml.features import SWING_WINDOW, add_indicators


# =========================================================
# CONFIGURACION
# =========================================================

@dataclass
class BacktestConfig:
    stop_atr: float = 2.0         # distancia del stop en ATR
    rr: float = 2.0               # objetivo en multiplos del riesgo
    max_bars: int = 20            # salida por tiempo
    cooldown: int = 0             # velas minimas entre entradas
    allow_overlap: bool = False   # permitir varias posiciones a la vez
    risk_pct: float = 1.0         # % del capital arriesgado por operacion
    fee_pct: float = 0.001        # comision por lado (0.1%)
    slippage_pct: float = 0.0005  # deslizamiento por lado (0.05%)
    initial_equity: float = 10000.0
    warmup: int = 210             # velas de calentamiento (EMA 200)


# =========================================================
# PREPARACION DE DATOS
# =========================================================

def prepare(df):
    """Indicadores + estructura vectorizada + regimen (todo sin mirar al futuro)."""
    d = add_indicators(df)
    d["Date"] = pd.to_datetime(d["Date"])

    # Swings confirmados (se conocen SWING_WINDOW velas despues)
    sh = d["High"].where(d["f_swing_high"]).shift(SWING_WINDOW)
    sl = d["Low"].where(d["f_swing_low"]).shift(SWING_WINDOW)
    sh_pts, sl_pts = sh.dropna(), sl.dropna()
    d["last_sh"] = sh_pts.reindex(d.index).ffill()
    d["prev_sh"] = sh_pts.shift(1).reindex(d.index).ffill()
    d["last_sl"] = sl_pts.reindex(d.index).ffill()
    d["prev_sl"] = sl_pts.shift(1).reindex(d.index).ffill()

    up = (d["last_sh"] > d["prev_sh"]) & (d["last_sl"] > d["prev_sl"])
    down = (d["last_sh"] < d["prev_sh"]) & (d["last_sl"] < d["prev_sl"])
    d["structure"] = np.where(up, 1, np.where(down, -1, 0))
    rng = d["last_sh"] - d["last_sl"]
    d["fib_pos"] = (d["Close"] - d["last_sl"]) / rng.where(rng > 0)

    # Regimen de tendencia
    c, e50, e200 = d["Close"], d["f_ema_50"], d["f_ema_200"]
    d["regime_trend"] = np.where((c > e200) & (e50 > e200), "ALCISTA",
                                 np.where((c < e200) & (e50 < e200), "BAJISTA", "MIXTO"))

    # Regimen de volatilidad: percentil del ATR% dentro de las ultimas 250 velas
    atr_pct = d["f_atr"] / c
    pct = atr_pct.rolling(250, min_periods=60).apply(lambda w: (w[-1] >= w).mean(), raw=True)
    d["regime_vol"] = np.where(pct >= 0.67, "ALTA", np.where(pct <= 0.33, "BAJA", "MEDIA"))
    d.loc[pct.isna(), "regime_vol"] = "N/D"
    return d


def periods_per_year(dates):
    dates = pd.to_datetime(pd.Series(dates))
    weekend = (dates.dt.dayofweek >= 5).mean()
    return 365 if weekend > 0.1 else 252


# =========================================================
# ESTRATEGIAS  (devuelven +1 / -1 / 0 al cierre de cada vela)
# =========================================================

def _s(long_cond, short_cond=None):
    sig = np.where(long_cond.fillna(False), 1, 0)
    if short_cond is not None:
        sig = np.where(short_cond.fillna(False) & (sig == 0), -1, sig)
    return pd.Series(sig, index=long_cond.index)


def strat_confluence_v2(d):
    """La estrategia original del proyecto (solo LONG), vectorizada."""
    bos = d["High"] > d["High"].shift(1).rolling(5).max()
    choch = d["Low"] > d["Low"].shift(1).rolling(5).min()
    fib = d["fib_pos"].between(0.382, 0.764)
    ema = d["f_ema_50"] > d["f_ema_200"]
    score = (2 * ema + (d["f_rsi"] > 50) + (d["f_adx"] > 35) + (d["f_rvol"] > 1.3)
             + 2 * bos + 2 * choch + fib)
    bias = ema.astype(int) + bos.astype(int) + choch.astype(int)
    return _s((score >= 6) & (bias >= 2))


def strat_confluence_sym(d):
    """Confluencia simetrica: mismas reglas en espejo para SHORT."""
    ema_up = d["f_ema_50"] > d["f_ema_200"]
    bos_up = d["High"] > d["High"].shift(1).rolling(5).max()
    ch_up = d["Low"] > d["Low"].shift(1).rolling(5).min()
    fib_l = d["fib_pos"].between(0.382, 0.764)
    s_long = (2 * ema_up + (d["f_rsi"] > 50) + (d["f_adx"] > 35) + (d["f_rvol"] > 1.3)
              + 2 * bos_up + 2 * ch_up + fib_l + (d["structure"] == 1))
    ema_dn = ~ema_up
    bos_dn = d["Low"] < d["Low"].shift(1).rolling(5).min()
    ch_dn = d["High"] < d["High"].shift(1).rolling(5).max()
    fib_s = d["fib_pos"].between(0.236, 0.618)
    s_short = (2 * ema_dn + (d["f_rsi"] < 50) + (d["f_adx"] > 35) + (d["f_rvol"] > 1.3)
               + 2 * bos_dn + 2 * ch_dn + fib_s + (d["structure"] == -1))
    return _s((s_long >= 7) & ema_up, (s_short >= 7) & ema_dn)


def strat_trend_pullback(d):
    """Tendencia + retroceso a la EMA20."""
    up = (d["f_ema_50"] > d["f_ema_200"]) & (d["Close"] > d["f_ema_200"])
    dn = (d["f_ema_50"] < d["f_ema_200"]) & (d["Close"] < d["f_ema_200"])
    long_ = up & (d["Low"] <= d["f_ema_20"]) & (d["Close"] > d["f_ema_20"]) & (d["f_rsi"] > 45)
    short = dn & (d["High"] >= d["f_ema_20"]) & (d["Close"] < d["f_ema_20"]) & (d["f_rsi"] < 55)
    return _s(long_, short)


def strat_donchian(d):
    """Ruptura de canal de 20 velas a favor de la tendencia."""
    hi = d["High"].shift(1).rolling(20).max()
    lo = d["Low"].shift(1).rolling(20).min()
    long_ = (d["Close"] > hi) & (d["f_adx"] > 20) & (d["f_ema_50"] > d["f_ema_200"])
    short = (d["Close"] < lo) & (d["f_adx"] > 20) & (d["f_ema_50"] < d["f_ema_200"])
    return _s(long_, short)


def strat_rsi_reversion(d):
    """Reversion: RSI sale de sobreventa/sobrecompra a favor de la EMA200."""
    r, r1 = d["f_rsi"], d["f_rsi"].shift(1)
    long_ = (r1 < 30) & (r >= 30) & (d["Close"] > d["f_ema_200"])
    short = (r1 > 70) & (r <= 70) & (d["Close"] < d["f_ema_200"])
    return _s(long_, short)


def strat_smc_structure(d):
    """Smart Money: estructura alcista/bajista + ruptura del ultimo swing."""
    cross_up = (d["Close"] > d["last_sh"]) & (d["Close"].shift(1) <= d["last_sh"])
    cross_dn = (d["Close"] < d["last_sl"]) & (d["Close"].shift(1) >= d["last_sl"])
    return _s((d["structure"] == 1) & cross_up, (d["structure"] == -1) & cross_dn)


STRATEGIES = {
    "confluencia_v2": {
        "fn": strat_confluence_v2, "label": "Confluencia v2 (original, LONG)",
        "cfg": dict(stop_atr=3.0, rr=2.0, max_bars=20, cooldown=30),
    },
    "confluencia_simetrica": {
        "fn": strat_confluence_sym, "label": "Confluencia simetrica (LONG/SHORT)",
        "cfg": dict(stop_atr=2.0, rr=2.0, max_bars=20, cooldown=10),
    },
    "tendencia_pullback": {
        "fn": strat_trend_pullback, "label": "Tendencia + pullback EMA20",
        "cfg": dict(stop_atr=1.5, rr=2.0, max_bars=20, cooldown=5),
    },
    "ruptura_donchian": {
        "fn": strat_donchian, "label": "Ruptura Donchian 20",
        "cfg": dict(stop_atr=2.0, rr=2.5, max_bars=30, cooldown=5),
    },
    "reversion_rsi": {
        "fn": strat_rsi_reversion, "label": "Reversion RSI 30/70",
        "cfg": dict(stop_atr=1.5, rr=1.5, max_bars=15, cooldown=5),
    },
    "estructura_smc": {
        "fn": strat_smc_structure, "label": "Estructura SMC (BOS confirmado)",
        "cfg": dict(stop_atr=2.0, rr=2.0, max_bars=25, cooldown=5),
    },
}


# =========================================================
# SIMULACION
# =========================================================

def run_backtest(d, signals, cfg=None, name="estrategia"):
    cfg = cfg or BacktestConfig()
    o = d["Open"].to_numpy(float)
    h = d["High"].to_numpy(float)
    lo = d["Low"].to_numpy(float)
    c = d["Close"].to_numpy(float)
    atr = d["f_atr"].to_numpy(float)
    dates = d["Date"].to_numpy()
    sig = np.asarray(signals, dtype=int)
    n = len(d)
    has_regime = "regime_trend" in d.columns

    trades = []
    last_entry = -10 ** 9
    busy_until = -1
    in_market = np.zeros(n, dtype=bool)

    i = cfg.warmup
    while i < n - 1:
        s = sig[i]
        if (
            s == 0 or not np.isfinite(atr[i]) or atr[i] <= 0
            or i - last_entry < cfg.cooldown
            or (not cfg.allow_overlap and i < busy_until)
        ):
            i += 1
            continue

        k = i + 1
        entry = o[k] * (1 + cfg.slippage_pct * s)
        risk = cfg.stop_atr * atr[i]
        stop = entry - s * risk
        target = entry + s * risk * cfg.rr

        last = min(k + cfg.max_bars - 1, n - 1)
        exit_px, reason, j = None, None, last
        mae = mfe = 0.0
        for j in range(k, last + 1):
            fav = (h[j] - entry) if s == 1 else (entry - lo[j])
            adv = (entry - lo[j]) if s == 1 else (h[j] - entry)
            mfe, mae = max(mfe, fav / risk), max(mae, adv / risk)
            if (lo[j] <= stop) if s == 1 else (h[j] >= stop):
                # gap en contra: se sale a la apertura si ya abrio mas alla del stop
                gap = (o[j] < stop) if s == 1 else (o[j] > stop)
                exit_px, reason = (o[j] if gap and j > k else stop), "SL"
                break
            if (h[j] >= target) if s == 1 else (lo[j] <= target):
                exit_px, reason = target, "TP"
                break
        if exit_px is None:
            exit_px = c[last]
            reason = "TIEMPO" if last - k + 1 >= cfg.max_bars else "FIN_DATOS"

        exit_eff = exit_px * (1 - cfg.slippage_pct * s)
        gross = s * (exit_eff - entry) / risk
        cost = cfg.fee_pct * (entry + exit_eff) / risk
        r = gross - cost

        in_market[k: j + 1] = True
        trades.append({
            "signal_time": dates[i],
            "entry_time": dates[k],
            "exit_time": dates[j],
            "direction": "LONG" if s == 1 else "SHORT",
            "entry": entry,
            "stop": stop,
            "target": target,
            "exit": exit_eff,
            "bars": j - k + 1,
            "reason": reason,
            "r_gross": gross,
            "cost_r": cost,
            "r": r,
            "mae_r": mae,
            "mfe_r": mfe,
            "regime_trend": d["regime_trend"].iloc[i] if has_regime else None,
            "regime_vol": d["regime_vol"].iloc[i] if has_regime else None,
        })
        last_entry = i
        busy_until = j + 1
        i += 1

    tdf = pd.DataFrame(trades)
    if len(tdf):
        tdf = tdf[tdf["reason"] != "FIN_DATOS"].reset_index(drop=True)
    return BacktestResult(name, cfg, tdf, d, float(in_market[cfg.warmup:].mean()) if n > cfg.warmup else 0.0)


class BacktestResult:
    def __init__(self, name, cfg, trades, d, exposure):
        self.name = name
        self.cfg = cfg
        self.trades = trades
        self.exposure = exposure
        self.calendar = pd.DatetimeIndex(d["Date"].iloc[cfg.warmup:])
        self.ppy = periods_per_year(d["Date"])
        self._stats = None
        self._eq = None

    @property
    def equity(self):
        if self._eq is None:
            self._eq = st.equity_from_trades(self.trades, self.cfg.risk_pct, self.cfg.initial_equity)
        return self._eq

    def stats(self, n_trials=1):
        if self._stats is None or self._stats.get("n_trials") != n_trials:
            s = st.trade_stats(self.trades["r"] if len(self.trades) else [], n_trials=n_trials)
            s.update(st.equity_stats(self.equity, self.cfg.initial_equity, self.ppy, self.calendar)
                     if len(self.trades) else {})
            s["exposure_pct"] = round(self.exposure * 100, 1)
            if len(self.trades):
                s["long_trades"] = int((self.trades["direction"] == "LONG").sum())
                s["short_trades"] = int((self.trades["direction"] == "SHORT").sum())
                s["avg_bars"] = round(float(self.trades["bars"].mean()), 1)
                s["cost_r_total"] = round(float(self.trades["cost_r"].sum()), 2)
            self._stats = s
        return self._stats

    def daily_equity(self):
        if len(self.trades) == 0:
            return pd.Series(self.cfg.initial_equity, index=self.calendar)
        return self.equity.reindex(self.calendar.union(self.equity.index)).ffill() \
            .reindex(self.calendar).fillna(self.cfg.initial_equity)


def buy_and_hold(d, initial=10000.0, warmup=210):
    px = d["Close"].iloc[warmup:]
    eq = pd.Series(initial * px.values / px.values[0], index=pd.DatetimeIndex(d["Date"].iloc[warmup:]))
    s = st.equity_stats(eq, initial, periods_per_year(d["Date"]), eq.index)
    return eq, s


# =========================================================
# COMPARACION / SENSIBILIDAD
# =========================================================

def config_for(key, **overrides):
    base = BacktestConfig(**STRATEGIES[key]["cfg"])
    return replace(base, **overrides) if overrides else base


def compare_strategies(df, keys=None, prepared=None, extra_trials=0, **overrides):
    """
    Corre todas las estrategias sobre los mismos datos.
    Devuelve (resultados dict, tabla resumen, benchmark (equity, stats), datos preparados).
    """
    d = prepared if prepared is not None else prepare(df)
    keys = keys or list(STRATEGIES)
    results = {}
    for k in keys:
        cfg = config_for(k, **overrides)
        results[k] = run_backtest(d, STRATEGIES[k]["fn"](d), cfg, STRATEGIES[k]["label"])

    n_trials = len(keys) + extra_trials
    rows = []
    for k, res in results.items():
        s = res.stats(n_trials=n_trials)
        rows.append({
            "estrategia": res.name, "clave": k,
            "trades": s.get("trades", 0),
            "win_rate": s.get("win_rate"),
            "expectancy_r": s.get("expectancy_r"),
            "exp_ci_low": (s.get("expectancy_ci") or (None, None))[0],
            "exp_ci_high": (s.get("expectancy_ci") or (None, None))[1],
            "profit_factor": s.get("profit_factor"),
            "sqn": s.get("sqn"),
            "p_value": s.get("p_value"),
            "psr": s.get("psr"),
            "dsr": s.get("dsr"),
            "cagr_pct": s.get("cagr_pct"),
            "sharpe": s.get("sharpe"),
            "max_dd_pct": s.get("max_drawdown_pct"),
            "calmar": s.get("calmar"),
            "exposicion_pct": s.get("exposure_pct"),
            "veredicto": s.get("verdict"),
        })
    table = pd.DataFrame(rows).sort_values(["expectancy_r"], ascending=False, na_position="last")
    bench = buy_and_hold(d)
    return results, table.reset_index(drop=True), bench, d


def parameter_grid(d, key, stops=(1.0, 1.5, 2.0, 3.0), rrs=(1.0, 1.5, 2.0, 3.0), **overrides):
    """
    Expectativa (R) para cada combinacion stop_atr x rr.
    Una estrategia robusta muestra una "meseta" positiva, no un pico aislado.
    """
    sig = STRATEGIES[key]["fn"](d)
    rows = []
    for sa in stops:
        for rr in rrs:
            cfg = config_for(key, stop_atr=sa, rr=rr, **overrides)
            t = run_backtest(d, sig, cfg).trades
            r = t["r"] if len(t) else pd.Series(dtype=float)
            rows.append({"stop_atr": sa, "rr": rr, "trades": len(r),
                         "expectancy_r": round(float(r.mean()), 3) if len(r) else np.nan,
                         "profit_factor": round(min(st._pf(r.values), 99), 2) if len(r) else np.nan})
    g = pd.DataFrame(rows)
    pivot = g.pivot(index="stop_atr", columns="rr", values="expectancy_r")
    positive = float((g["expectancy_r"] > 0).mean() * 100) if len(g) else 0.0
    return g, pivot, round(positive, 1)


def full_research(df, key=None, symbol="", n_mc=5000):
    """
    Paquete completo para el reporte: comparacion, mejor estrategia,
    Monte Carlo, walk-forward, regimenes, sensibilidad, riesgo de ruina.
    """
    grid_trials = 16
    results, table, bench, d = compare_strategies(df, extra_trials=grid_trials)
    if key is None:
        valid = table[table["trades"] >= 20]
        key = (valid.iloc[0]["clave"] if len(valid) else table.iloc[0]["clave"])
    best = results[key]
    t = best.trades
    s = best.stats(n_trials=len(results) + grid_trials)
    out = {
        "symbol": symbol,
        "results": results,
        "table": table,
        "benchmark": bench,
        "prepared": d,
        "key": key,
        "best": best,
        "stats": s,
        "config": asdict(best.cfg),
    }
    if len(t) >= 5:
        out["monte_carlo"] = st.monte_carlo(t["r"], best.cfg.risk_pct, n_sims=n_mc)
        out["ruin_table"] = st.risk_of_ruin_table(t["r"])
        out["segments"] = st.walk_forward_segments(t)
        out["stability"] = st.stability_score(out["segments"])
        out["regime_trend"] = st.regime_breakdown(t, "regime_trend")
        out["regime_vol"] = st.regime_breakdown(t, "regime_vol")
        out["by_direction"] = st.regime_breakdown(t, "direction")
        out["by_reason"] = st.regime_breakdown(t, "reason")
    grid, pivot, pos = parameter_grid(d, key)
    out["grid"], out["grid_pivot"], out["grid_positive_pct"] = grid, pivot, pos
    return out
