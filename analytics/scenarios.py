"""
Escenarios y probabilidades del PRESENTE.

Para la situacion actual de un activo responde:
  - Que paso historicamente en situaciones parecidas? (analogos, k-vecinos)
  - Cual es la probabilidad base si el precio fuese aleatorio con la
    volatilidad actual? (Monte Carlo por bootstrap de velas)
  - Probabilidad de tocar TP1/TP2/TP3 antes que el stop, para LONG y SHORT.
  - Valor esperado (R), ventaja sobre el azar, Kelly y un Decision Score.
  - Cono de precios a 5/10/20 velas.

La probabilidad final combina ambas fuentes con contraccion bayesiana:
    p = (aciertos_analogos + K * p_base) / (n_analogos + K)
de modo que con pocos analogos domina la probabilidad base (prudente).
"""

import math

import numpy as np
import pandas as pd

SHRINK_K = 30          # "operaciones virtuales" del prior
HORIZONS = (5, 10, 20)


# =========================================================
# FEATURES VECTORIZADAS PARA SIMILITUD
# =========================================================

SIM_FEATURES = [
    "z_ema20", "z_ema50", "z_ema200", "slope50", "rsi", "macd_h", "adx", "di_diff",
    "log_rvol", "bb_pctb", "ret5", "ret20", "structure", "fib_pos", "range50", "vol_ratio",
]


_sim_cache = {}


def similarity_frame(d):
    key = (id(d), len(d))
    if key in _sim_cache:
        return _sim_cache[key]
    if len(_sim_cache) > 300:
        _sim_cache.clear()
    f = _similarity_frame(d)
    _sim_cache[key] = f
    return f


def _similarity_frame(d):
    atr = d["f_atr"].replace(0, np.nan)
    c = d["Close"]
    f = pd.DataFrame(index=d.index)
    f["z_ema20"] = (c - d["f_ema_20"]) / atr
    f["z_ema50"] = (c - d["f_ema_50"]) / atr
    f["z_ema200"] = (c - d["f_ema_200"]) / atr
    f["slope50"] = (d["f_ema_50"] - d["f_ema_50"].shift(5)) / atr
    f["rsi"] = d["f_rsi"]
    f["macd_h"] = d["f_macd_hist"] / atr
    f["adx"] = d["f_adx"]
    f["di_diff"] = d["f_plus_di"] - d["f_minus_di"]
    f["log_rvol"] = np.log(d["f_rvol"].clip(lower=0.05))
    width = d["f_bb_upper"] - d["f_bb_lower"]
    f["bb_pctb"] = (c - d["f_bb_lower"]) / width.where(width > 0)
    # retornos medidos en ATR: comparables entre activos de distinta volatilidad
    f["ret5"] = (c - c.shift(5)) / atr
    f["ret20"] = (c - c.shift(20)) / atr
    f["structure"] = d["structure"] if "structure" in d else 0
    f["fib_pos"] = d["fib_pos"].clip(-1, 2) if "fib_pos" in d else np.nan
    hi, lo = d["High"].rolling(50).max(), d["Low"].rolling(50).min()
    f["range50"] = (c - lo) / (hi - lo).where(hi > lo)
    f["vol_ratio"] = d["f_hv20"] / d["f_hv100"]
    return f.replace([np.inf, -np.inf], np.nan)


# =========================================================
# RESULTADOS HACIA ADELANTE (historicos)
# =========================================================

_arr_cache = {}


def _arrays(d):
    key = (id(d), len(d))
    if key not in _arr_cache:
        if len(_arr_cache) > 300:
            _arr_cache.clear()
        _arr_cache[key] = tuple(d[k].to_numpy(float) for k in ("High", "Low", "Close", "f_atr"))
    return _arr_cache[key]


def forward_outcomes(d, direction, stop_atr, targets_r, max_bars=20, idx=None):
    """
    Para cada vela i (entrada al cierre): el R obtenido y, para cada objetivo,
    si se toco antes que el stop. NaN donde no hay suficientes velas futuras.
    `idx`: calcular solo esas velas (mucho mas rapido para analogos).
    """
    h, lo, c, atr = _arrays(d)
    n = len(d)
    s = 1 if direction == "LONG" else -1
    tmax = max(targets_r)
    hit = np.full((n, len(targets_r)), np.nan)
    r_out = np.full(n, np.nan)
    rng = range(n - max_bars) if idx is None else [i for i in idx if 0 <= i < n - max_bars]
    for i in rng:
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        e, risk = c[i], stop_atr * atr[i]
        stop = e - s * risk
        reached = np.zeros(len(targets_r))
        done = False
        for j in range(i + 1, i + 1 + max_bars):
            fav = ((h[j] - e) if s == 1 else (e - lo[j])) / risk
            stop_hit = lo[j] <= stop if s == 1 else h[j] >= stop
            if stop_hit:
                done = True
                r_out[i] = -1.0
                break
            for t, tr in enumerate(targets_r):
                if fav >= tr:
                    reached[t] = 1
            if fav >= tmax:
                done = True
                r_out[i] = tmax
                break
        hit[i] = reached
        if not done:
            r_out[i] = s * (c[i + max_bars] - e) / risk
    return hit, r_out


def forward_returns(d, horizons=HORIZONS):
    c = d["Close"]
    return pd.DataFrame({h: c.shift(-h) / c - 1 for h in horizons})


# =========================================================
# ANALOGOS
# =========================================================

UNIVERSE_EXCLUDE = {"log_rvol"}   # el volumen no es comparable entre clases de activo


def find_analogs(pool, symbol, k=60, min_gap=5, max_bars=20, max_per_asset=None):
    """
    Busca en `pool` ({simbolo: DataFrame preparado}) las k velas historicas
    mas parecidas a la ULTIMA vela de `pool[symbol]`.

    - Features robustas estandarizadas (mediana/IQR del pool completo).
    - Separacion minima de `min_gap` velas entre analogos del mismo activo.
    - Tope de analogos por activo para diversificar los casos de estudio.
    Devuelve (lista [(simbolo, indice)], Serie de distancias, columnas usadas).
    """
    d_cur = pool[symbol]
    f_cur = similarity_frame(d_cur)
    cur = f_cur.iloc[-1]
    multi = len(pool) > 1
    cols = [c for c in SIM_FEATURES if pd.notna(cur.get(c)) and not (multi and c in UNIVERSE_EXCLUDE)]
    if not cols:
        return [], pd.Series(dtype=float), cols

    parts = []
    for sym, d in pool.items():
        f = f_cur if sym == symbol else similarity_frame(d)
        h = f.iloc[200: max(200, len(d) - max_bars)][cols].dropna()
        if len(h):
            h = h.copy()
            h["_sym"] = sym
            h["_idx"] = h.index
            parts.append(h)
    if not parts:
        return [], pd.Series(dtype=float), cols
    hist = pd.concat(parts, ignore_index=True)
    if len(hist) < 50:
        return [], pd.Series(dtype=float), cols

    X = hist[cols]
    med = X.median()
    iqr = (X.quantile(0.75) - X.quantile(0.25)).replace(0, 1)
    z = (X - med) / iqr
    zc = (cur[cols].astype(float) - med) / iqr
    dist = np.sqrt(((z - zc) ** 2).sum(axis=1)).sort_values()

    max_per_asset = max_per_asset or (max(10, k // 4) if multi else k)
    chosen, per_asset, taken = [], {}, {}
    for pos in dist.index:
        sym, idx = hist.at[pos, "_sym"], int(hist.at[pos, "_idx"])
        if per_asset.get(sym, 0) >= max_per_asset:
            continue
        if any(abs(idx - j) < min_gap for j in taken.get(sym, [])):
            continue
        chosen.append((sym, idx))
        taken.setdefault(sym, []).append(idx)
        per_asset[sym] = per_asset.get(sym, 0) + 1
        if len(chosen) >= k:
            break
    dist_by_key = pd.Series({(hist.at[p, "_sym"], int(hist.at[p, "_idx"])): dist[p] for p in dist.index[: k * 20]})
    return chosen, dist_by_key, cols


def effective_n(pool, analogs):
    """
    Analogos del mismo periodo (p. ej. BTC y ETH la misma semana) no son
    independientes: se cuentan las semanas distintas.
    """
    if not analogs:
        return 0
    weeks = {pd.Timestamp(pool[s]["Date"].iloc[i]).to_period("W") for s, i in analogs}
    return len(weeks)




def analog_outcomes(pool, analogs, direction, stop_atr, targets_r, max_bars):
    """Resultados (aciertos por objetivo y R) de cada analogo."""
    hits = np.full((len(analogs), len(targets_r)), np.nan)
    rs = np.full(len(analogs), np.nan)
    by_sym = {}
    for n, (s, i) in enumerate(analogs):
        by_sym.setdefault(s, []).append((n, i))
    for s, items in by_sym.items():
        h, r = forward_outcomes(pool[s], direction, stop_atr, targets_r, max_bars, idx=[i for _, i in items])
        for n, i in items:
            hits[n], rs[n] = h[i], r[i]
    return hits, rs


# =========================================================
# POOL DEL UNIVERSO
# =========================================================

_pool_cache = {"key": None, "pool": None}


def get_universe_pool(symbols=None, loader=None, progress=None):
    """
    Carga y prepara todos los activos del universo (usa la cache de datos).
    Se reutiliza en memoria durante la sesion.
    """
    from backtesting.engine import prepare
    from config import settings
    symbols = list(symbols or settings.WATCHLIST)
    stamp = pd.Timestamp.now().floor(f"{int(settings.CACHE_MAX_AGE_HOURS)}h")
    key = (tuple(symbols), settings.INTERVAL, settings.PERIOD, stamp, id(loader))
    if _pool_cache["key"] == key:
        return _pool_cache["pool"]
    if loader is None:
        from data.cache import load_many
        frames, _ = load_many(symbols, progress=progress, log=lambda *x: None)
    else:
        frames = {}
        for s in symbols:
            try:
                frames[s] = loader(s, settings.PERIOD, settings.INTERVAL)
            except Exception:  # noqa: BLE001
                continue
    pool = {}
    for s, df in frames.items():
        if df is not None and len(df) > 300:
            try:
                pool[s] = prepare(df)
            except Exception:  # noqa: BLE001
                continue
    _pool_cache.update(key=key, pool=pool)
    return pool


# =========================================================
# MONTE CARLO DE PRECIO
# =========================================================

def simulate_paths(d, n_paths=4000, n_bars=20, lookback=750, block=5, demean=True, seed=3):
    """
    Bootstrap por bloques de velas relativas al cierre previo, reescaladas a la
    volatilidad actual. Devuelve arrays (n_paths, n_bars) de open/high/low/close
    relativos al precio actual (1.0 = precio actual).
    """
    x = d.iloc[-(lookback + 1):]
    pc = x["Close"].shift(1)
    rel = np.log(np.column_stack([x["Open"] / pc, x["High"] / pc, x["Low"] / pc, x["Close"] / pc]))[1:]
    rel = rel[np.isfinite(rel).all(axis=1)]
    if len(rel) < 60:
        return None
    if demean:
        rel = rel - rel[:, 3].mean()
    atr_pct = (d["f_atr"] / d["Close"]).iloc[-(lookback + 1):]
    scale = float(atr_pct.iloc[-1] / atr_pct.mean()) if atr_pct.mean() > 0 else 1.0
    scale = float(np.clip(scale, 0.5, 2.0))
    rel = rel * scale

    rng = np.random.default_rng(seed)
    nb = math.ceil(n_bars / block)
    starts = rng.integers(0, len(rel) - block, size=(n_paths, nb))
    idx = (starts[:, :, None] + np.arange(block)).reshape(n_paths, -1)[:, :n_bars]
    steps = rel[idx]                                   # (paths, bars, 4)
    close_log = np.cumsum(steps[:, :, 3], axis=1)
    prev = np.concatenate([np.zeros((n_paths, 1)), close_log[:, :-1]], axis=1)
    return {
        "open": np.exp(prev + steps[:, :, 0]),
        "high": np.exp(prev + np.maximum(steps[:, :, 1], np.maximum(steps[:, :, 0], steps[:, :, 3]))),
        "low": np.exp(prev + np.minimum(steps[:, :, 2], np.minimum(steps[:, :, 0], steps[:, :, 3]))),
        "close": np.exp(close_log),
        "scale": scale,
    }


def mc_first_passage(paths, direction, stop_rel, targets_rel):
    """Probabilidad de tocar cada objetivo antes que el stop (criterio conservador)."""
    s = 1 if direction == "LONG" else -1
    hi, lo, cl = paths["high"], paths["low"], paths["close"]
    n_paths, n_bars = cl.shape
    stop_hit = (lo <= 1 - stop_rel) if s == 1 else (hi >= 1 + stop_rel)
    first_stop = np.where(stop_hit.any(axis=1), stop_hit.argmax(axis=1), n_bars)
    probs, r_mean = [], None
    for tr in targets_rel:
        t_hit = (hi >= 1 + tr) if s == 1 else (lo <= 1 - tr)
        first_t = np.where(t_hit.any(axis=1), t_hit.argmax(axis=1), n_bars)
        probs.append(float(((first_t < first_stop) & (first_t < n_bars)).mean()))
    # R esperado con el objetivo mas lejano
    tr = targets_rel[-1]
    t_hit = (hi >= 1 + tr) if s == 1 else (lo <= 1 - tr)
    first_t = np.where(t_hit.any(axis=1), t_hit.argmax(axis=1), n_bars)
    win = (first_t < first_stop) & (first_t < n_bars)
    loss = (first_stop <= first_t) & (first_stop < n_bars)
    other = ~(win | loss)
    r = np.where(win, tr / stop_rel, np.where(loss, -1.0, s * (cl[:, -1] - 1) / stop_rel))
    r_mean = float(r.mean())
    return probs, r_mean, float(other.mean()), float((r ** 2).mean())


def price_cone(paths, last_price, horizons=HORIZONS, q=(5, 25, 50, 75, 95)):
    out = {}
    for h in horizons:
        if h <= paths["close"].shape[1]:
            v = paths["close"][:, h - 1] * last_price
            out[h] = {p: float(np.percentile(v, p)) for p in q}
    full = {p: np.percentile(paths["close"], p, axis=0) * last_price for p in q}
    return out, full


# =========================================================
# ESCENARIO COMPLETO
# =========================================================

def evaluate_direction(d, direction, stop_atr, targets_r, paths, pool, analogs, max_bars, fee_pct=0.001):
    last = d.iloc[-1]
    price, atr = float(last["Close"]), float(last["f_atr"])
    risk = stop_atr * atr
    s = 1 if direction == "LONG" else -1
    stop_rel = risk / price
    targets_rel = [t * risk / price for t in targets_r]

    base_p, base_r, base_timeout, base_r2 = mc_first_passage(paths, direction, stop_rel, targets_rel)
    hit, r_hist = analog_outcomes(pool, analogs, direction, stop_atr, targets_r, max_bars)

    ok = np.isfinite(r_hist)
    hit, r_hist = hit[ok], r_hist[ok]
    valid = [a for a, v in zip(analogs, ok) if v]
    n = len(r_hist)
    n_eff = effective_n(pool, valid)
    # peso de la evidencia de los analogos = casos efectivamente independientes
    w = n_eff

    rows = []
    for t, tr in enumerate(targets_r):
        p_an = float(np.nanmean(hit[:, t])) if n else None
        p = ((p_an or 0) * w + SHRINK_K * base_p[t]) / (w + SHRINK_K)
        rows.append({
            "objetivo": f"{tr:g}R",
            "precio": round(price + s * tr * risk, 6),
            "p_analogos": round(p_an, 4) if p_an is not None else None,
            "p_base_aleatoria": round(base_p[t], 4),
            "p_final": round(p, 4),
            "ventaja": round(p - base_p[t], 4),
        })

    r_an = float(np.nanmean(r_hist)) if n else None
    ev = ((r_an if r_an is not None else 0) * w + SHRINK_K * base_r) / (w + SHRINK_K)
    cost_r = fee_pct * 2 * price / risk
    ev_net = ev - cost_r

    main = rows[min(1, len(rows) - 1)]           # objetivo principal: 2R (TP2)
    p_main = main["p_final"]
    # Kelly continuo: f* = E[R] / E[R^2]  (coherente con timeouts y R fraccionarios)
    r2_an = float(np.nanmean(r_hist ** 2)) if n else 0.0
    r2 = (r2_an * w + SHRINK_K * base_r2) / (w + SHRINK_K)
    kelly = ev_net / r2 if r2 > 0 else 0.0
    wins = int(round(float(np.nanmean(hit[:, min(1, len(targets_r) - 1)])) * n_eff)) if n else 0

    from analytics.stats import wilson_ci
    return {
        "direction": direction,
        "entry": price,
        "stop": price - s * risk,
        "risk_per_unit": risk,
        "targets": rows,
        "n_analogs": n,
        "n_effective": n_eff,
        "n_assets": len({a[0] for a in valid}),
        "analog_expectancy_r": round(r_an, 4) if r_an is not None else None,
        "analog_win_ci": wilson_ci(wins, n_eff) if n_eff else (None, None),
        "base_expectancy_r": round(base_r, 4),
        "base_timeout_pct": round(base_timeout * 100, 1),
        "ev_r": round(ev, 4),
        "cost_r": round(cost_r, 4),
        "ev_net_r": round(ev_net, 4),
        "p_main": p_main,
        "edge_main": main["ventaja"],
        "kelly": round(kelly, 4),
        "half_kelly_pct": round(max(0.0, kelly / 2) * 100, 2),
    }


def decision_score(ev_net_r, edge, confluence=None, model_p=None, p_main=None):
    ev_part = 50 + 50 * math.tanh(ev_net_r / 0.4)
    edge_part = 50 + 50 * math.tanh(edge / 0.08)
    parts = [(ev_part, 0.5), (edge_part, 0.25)]
    if confluence is not None:
        parts.append((confluence, 0.25))
    if model_p is not None and p_main is not None:
        parts.append((50 + 50 * math.tanh((model_p - 0.5) / 0.1), 0.2))
    w = sum(p[1] for p in parts)
    return round(sum(v * wt for v, wt in parts) / w, 1)


def verdict(ev_net_r, edge, n_analogs):
    if n_analogs < 15:
        return "DATOS INSUFICIENTES"
    if ev_net_r > 0.15 and edge > 0.03:
        return "FAVORABLE"
    if ev_net_r > 0.03:
        return "MARGINAL"
    if ev_net_r > -0.05:
        return "NEUTRAL"
    return "DESFAVORABLE"


def build_scenarios(d, stop_atr=2.0, targets_r=(1.0, 2.0, 2.5), max_bars=20, k=60,
                    confluence=None, model_probs=None, n_paths=4000, fee_pct=0.001,
                    pool=None, symbol="ACTUAL"):
    """
    d: DataFrame preparado (backtesting.engine.prepare) del activo analizado.
    pool: {simbolo: DataFrame preparado} para buscar analogos en otros activos.
          Si es None, solo se busca en el propio activo.
    confluence / model_probs: dict {"LONG": x, "SHORT": y} opcionales.
    """
    paths = simulate_paths(d, n_paths=n_paths, n_bars=max_bars)
    if paths is None:
        return None
    pool = dict(pool or {})
    pool[symbol] = d                     # el activo actual siempre con sus datos exactos
    analogs, dist, cols = find_analogs(pool, symbol, k=k, max_bars=max_bars)

    out = {"price": float(d["Close"].iloc[-1]), "date": pd.Timestamp(d["Date"].iloc[-1]),
           "atr": float(d["f_atr"].iloc[-1]), "vol_scale": paths["scale"],
           "n_analogs": len(analogs), "n_effective": effective_n(pool, analogs),
           "n_assets": len({a[0] for a in analogs}), "pool_size": len(pool),
           "scope": "universo" if len(pool) > 1 else "activo",
           "features_used": cols, "directions": {}}

    for direction in ("LONG", "SHORT"):
        ev = evaluate_direction(d, direction, stop_atr, list(targets_r), paths, pool, analogs, max_bars, fee_pct)
        conf = (confluence or {}).get(direction)
        mp = (model_probs or {}).get(direction)
        ev["confluence"] = conf
        ev["model_p"] = mp
        ev["score"] = decision_score(ev["ev_net_r"], ev["edge_main"], conf, mp, ev["p_main"])
        ev["verdict"] = verdict(ev["ev_net_r"], ev["edge_main"], ev["n_effective"])
        out["directions"][direction] = ev

    best = max(out["directions"].values(), key=lambda e: e["score"])
    out["best_direction"] = best["direction"]
    out["best"] = best

    # Distribucion futura: analogos (retornos en % de cada activo) vs aleatorio
    fr_cache = {}

    def fwd(sym, i, h):
        if sym not in fr_cache:
            fr_cache[sym] = forward_returns(pool[sym])
        v = fr_cache[sym][h].iloc[i]
        return float(v) if pd.notna(v) else np.nan

    cone, cone_full = price_cone(paths, out["price"])
    out["cone"], out["cone_full"] = cone, cone_full
    # los retornos de otros activos se reescalan a la volatilidad del activo actual
    atr_pct_now = out["atr"] / out["price"]

    def scaled(sym, i, h):
        v = fwd(sym, i, h)
        a_pct = float(pool[sym]["f_atr"].iloc[i] / pool[sym]["Close"].iloc[i])
        return v * (atr_pct_now / a_pct) if a_pct > 0 and np.isfinite(v) else np.nan

    dist_rows = []
    for h in HORIZONS:
        vals = pd.Series([scaled(s, i, h) for s, i in analogs]).dropna() if analogs else pd.Series(dtype=float)
        row = {"horizonte": h}
        if len(vals):
            row.update({
                "analogos_p_sube": round(float((vals > 0).mean()), 3),
                "analogos_mediana_%": round(float(vals.median() * 100), 2),
                "analogos_p10_%": round(float(vals.quantile(0.1) * 100), 2),
                "analogos_p90_%": round(float(vals.quantile(0.9) * 100), 2),
            })
        if h in cone:
            row["aleatorio_p5"] = round(cone[h][5], 6)
            row["aleatorio_p50"] = round(cone[h][50], 6)
            row["aleatorio_p95"] = round(cone[h][95], 6)
        dist_rows.append(row)
    out["forward"] = pd.DataFrame(dist_rows)

    if analogs:
        _, rL = analog_outcomes(pool, analogs[:15], "LONG", stop_atr, list(targets_r), max_bars)
        _, rS = analog_outcomes(pool, analogs[:15], "SHORT", stop_atr, list(targets_r), max_bars)
        top = []
        for n, (s, i) in enumerate(analogs[:15]):
            r20 = fwd(s, i, 20)
            top.append({
                "activo": s,
                "fecha": pd.Timestamp(pool[s]["Date"].iloc[i]).date(),
                "distancia": round(float(dist.get((s, i), np.nan)), 2),
                "precio": round(float(pool[s]["Close"].iloc[i]), 4),
                "ret_20v_%": round(r20 * 100, 2) if np.isfinite(r20) else None,
                "R_long": round(float(rL[n]), 2) if np.isfinite(rL[n]) else None,
                "R_short": round(float(rS[n]), 2) if np.isfinite(rS[n]) else None,
            })
        out["analog_table"] = pd.DataFrame(top)
        out["analog_returns_20"] = pd.Series([scaled(s, i, 20) for s, i in analogs]).dropna().values
        counts = pd.Series([s for s, _ in analogs]).value_counts()
        out["analog_assets"] = counts.rename_axis("activo").reset_index(name="analogos")
    return out


def scenario_summary_row(symbol, sc):
    b = sc["best"]
    L, S = sc["directions"]["LONG"], sc["directions"]["SHORT"]
    return {
        "activo": symbol,
        "precio": round(sc["price"], 4),
        "mejor": b["direction"],
        "veredicto": b["verdict"],
        "score": b["score"],
        "ev_neto_R": b["ev_net_r"],
        "p_TP2": b["p_main"],
        "ventaja": b["edge_main"],
        "analogos": b["n_analogs"],
        "casos_efectivos": b.get("n_effective"),
        "score_long": L["score"],
        "score_short": S["score"],
        "medio_kelly_%": b["half_kelly_pct"],
    }
