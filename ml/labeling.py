"""
Etiquetado de resultados.

Dado un plan (direccion, entrada, stop, objetivo) y las velas POSTERIORES,
determina que paso: WIN / LOSS / TIMEOUT, el resultado en R, cuantas velas
duro, y la excursion adversa/favorable maxima (MAE / MFE) en R.

Criterio conservador: si en la misma vela se tocan stop y objetivo,
se asume que primero salto el stop.
"""

import numpy as np
import pandas as pd


def simulate_outcome(future, direction, entry, stop, target, max_bars=20):
    """
    future: DataFrame con High/Low/Close de las velas posteriores a la entrada.
    Devuelve dict o None si no hay velas suficientes.
    """

    direction = str(direction).upper()
    entry, stop, target = float(entry), float(stop), float(target)

    risk = abs(entry - stop)
    if risk <= 0 or future is None or len(future) == 0:
        return None

    future = future.iloc[:max_bars]
    sign = 1 if direction == "LONG" else -1

    mae = 0.0
    mfe = 0.0

    for n, (_, bar) in enumerate(future.iterrows(), start=1):

        high, low = float(bar["High"]), float(bar["Low"])

        fav = (high - entry) if sign == 1 else (entry - low)
        adv = (entry - low) if sign == 1 else (high - entry)
        mfe = max(mfe, fav / risk)
        mae = max(mae, adv / risk)

        hit_stop = low <= stop if sign == 1 else high >= stop
        hit_target = high >= target if sign == 1 else low <= target

        if hit_stop:
            return _result("LOSS", -1.0, n, mae, mfe, stop, bar)

        if hit_target:
            r = abs(target - entry) / risk
            return _result("WIN", r, n, mae, mfe, target, bar)

    last = future.iloc[-1]
    close = float(last["Close"])
    r = sign * (close - entry) / risk

    if len(future) < max_bars:
        status = "OPEN"          # aun no hay suficientes velas
    else:
        status = "TIMEOUT"

    return _result(status, r, len(future), mae, mfe, close, last)


def _result(status, r, bars, mae, mfe, exit_price, bar):
    return {
        "outcome": status,
        "r_result": round(float(r), 4),
        "bars": int(bars),
        "mae_r": round(float(mae), 4),
        "mfe_r": round(float(mfe), 4),
        "exit_price": float(exit_price),
        "exit_time": bar["Date"] if "Date" in bar.index else None,
    }


def excursions(df_between, direction, entry, stop):
    """MAE/MFE (en R) de una operacion real entre su entrada y su salida."""

    risk = abs(float(entry) - float(stop))
    if risk <= 0 or df_between is None or len(df_between) == 0:
        return None, None

    if str(direction).upper() == "LONG":
        mfe = (df_between["High"].max() - entry) / risk
        mae = (entry - df_between["Low"].min()) / risk
    else:
        mfe = (entry - df_between["Low"].min()) / risk
        mae = (df_between["High"].max() - entry) / risk

    return round(float(max(mae, 0)), 4), round(float(max(mfe, 0)), 4)


def label_market_samples(df_ind, symbol, stride=5, stop_atr=1.5, rr=2.0,
                         max_bars=20, warmup=210):
    """
    Genera muestras historicas: en cada `stride` velas se simula
    un LONG y un SHORT con stop a `stop_atr` ATR y objetivo a `rr` R.
    Devuelve lista de dicts (sin features; las agrega dataset.py).
    """

    samples = []
    n = len(df_ind)

    for i in range(warmup, n - max_bars, stride):

        atr = df_ind["f_atr"].iloc[i]
        if pd.isna(atr) or atr <= 0:
            continue

        entry = float(df_ind["Close"].iloc[i])
        future = df_ind.iloc[i + 1: i + 1 + max_bars]

        for direction in ("LONG", "SHORT"):

            sign = 1 if direction == "LONG" else -1
            stop = entry - sign * stop_atr * atr
            target = entry + sign * stop_atr * atr * rr

            out = simulate_outcome(future, direction, entry, stop, target, max_bars)
            if out is None or out["outcome"] == "OPEN":
                continue

            samples.append({
                "index": i,
                "time": df_ind["Date"].iloc[i],
                "symbol": symbol,
                "direction": direction,
                "entry": entry,
                "stop": stop,
                "target": target,
                **out,
            })

    return samples
