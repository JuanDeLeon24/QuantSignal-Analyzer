"""
Ingenieria de features de QuantSignal AI.

Regla de oro: las MISMAS features se calculan para
  - las senales que genera el analizador,
  - las operaciones que registras tu manualmente,
  - las muestras historicas del mercado.
Asi la IA puede aprender de las tres fuentes con un unico esquema.

Todas las features en la vela i usan solo informacion disponible
al cierre de la vela i (sin mirar al futuro). Los swings solo se
cuentan cuando ya estan confirmados.

Implementado solo con pandas/numpy (no depende de la libreria `ta`).
"""

import numpy as np
import pandas as pd

FEATURE_VERSION = "1.0"

SWING_WINDOW = 3

EMA_PERIODS = [20, 50, 100, 200]


# =========================================================
# INDICADORES
# =========================================================

def _wilder(series, period):
    return series.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def add_indicators(df):
    """
    Agrega todas las columnas tecnicas necesarias para las features.
    Recibe OHLCV con columna Date. Devuelve una copia.
    """

    df = df.copy()

    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    volume = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series(0.0, index=df.index)

    for p in EMA_PERIODS:
        df[f"f_ema_{p}"] = close.ewm(span=p, adjust=False).mean()

    # RSI (Wilder)
    delta = close.diff()
    gain = _wilder(delta.clip(lower=0), 14)
    loss = _wilder(-delta.clip(upper=0), 14)
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    rsi = rsi.where(~((loss == 0) & gain.notna()), 100.0)
    df["f_rsi"] = rsi

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    df["f_macd"] = macd
    df["f_macd_signal"] = macd_signal
    df["f_macd_hist"] = macd - macd_signal

    # ATR
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    df["f_atr"] = _wilder(tr, 14)

    # ADX / DI
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    atr_w = _wilder(tr, 14)
    plus_di = 100 * _wilder(plus_dm, 14) / atr_w
    minus_di = 100 * _wilder(minus_dm, 14) / atr_w
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    df["f_plus_di"] = plus_di
    df["f_minus_di"] = minus_di
    df["f_adx"] = _wilder(dx.fillna(0), 14)

    # Bollinger
    ma20 = close.rolling(20).mean()
    sd20 = close.rolling(20).std()
    df["f_bb_upper"] = ma20 + 2 * sd20
    df["f_bb_lower"] = ma20 - 2 * sd20

    # Volumen
    df["f_vol_ma"] = volume.rolling(20).mean()
    df["f_rvol"] = volume / df["f_vol_ma"].replace(0, np.nan)

    # Volatilidad historica (desv. de retornos)
    ret = close.pct_change()
    df["f_hv20"] = ret.rolling(20).std()
    df["f_hv100"] = ret.rolling(100).std()

    # Swings (centrados: se CONFIRMAN SWING_WINDOW velas despues)
    w = SWING_WINDOW * 2 + 1
    df["f_swing_high"] = high == high.rolling(w, center=True).max()
    df["f_swing_low"] = low == low.rolling(w, center=True).min()

    return df


# =========================================================
# FEATURES POR VELA
# =========================================================

def _safe(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return np.nan
    return x if np.isfinite(x) else np.nan


def _confirmed_swings(df, i):
    """Swings conocidos al cierre de la vela i."""
    last_visible = i - SWING_WINDOW
    if last_visible < 0:
        return df.iloc[0:0], df.iloc[0:0]
    part = df.iloc[: last_visible + 1]
    return part[part["f_swing_high"]], part[part["f_swing_low"]]


def feature_row(df, i):
    """
    Vector de features (dict) en la vela i. `df` debe venir de add_indicators.
    """

    row = df.iloc[i]
    close = _safe(row["Close"])
    atr = _safe(row["f_atr"])
    atr_ok = atr if atr and atr > 0 else np.nan

    f = {}

    # --- Tendencia
    for p in EMA_PERIODS:
        f[f"dist_ema{p}_atr"] = (close - _safe(row[f"f_ema_{p}"])) / atr_ok

    f["ema20_gt_ema50"] = float(row["f_ema_20"] > row["f_ema_50"])
    f["ema50_gt_ema200"] = float(row["f_ema_50"] > row["f_ema_200"])

    if i >= 5:
        prev = df.iloc[i - 5]
        f["ema50_slope_atr"] = (_safe(row["f_ema_50"]) - _safe(prev["f_ema_50"])) / atr_ok
        f["ema200_slope_atr"] = (_safe(row["f_ema_200"]) - _safe(prev["f_ema_200"])) / atr_ok
    else:
        f["ema50_slope_atr"] = np.nan
        f["ema200_slope_atr"] = np.nan

    # --- Momentum
    f["rsi"] = _safe(row["f_rsi"])
    f["macd_hist_atr"] = _safe(row["f_macd_hist"]) / atr_ok
    f["macd_above_signal"] = float(row["f_macd"] > row["f_macd_signal"])
    for n in [1, 5, 20]:
        f[f"ret_{n}"] = (close / _safe(df["Close"].iloc[i - n]) - 1) if i >= n else np.nan

    # --- Fuerza de tendencia
    f["adx"] = _safe(row["f_adx"])
    f["di_diff"] = _safe(row["f_plus_di"]) - _safe(row["f_minus_di"])

    # --- Volatilidad
    f["atr_pct"] = atr / close if close else np.nan
    bb_u, bb_l = _safe(row["f_bb_upper"]), _safe(row["f_bb_lower"])
    width = bb_u - bb_l
    f["bb_pctb"] = (close - bb_l) / width if width and width > 0 else np.nan
    f["bb_width_pct"] = width / close if close else np.nan
    hv20, hv100 = _safe(row["f_hv20"]), _safe(row["f_hv100"])
    f["vol_regime"] = hv20 / hv100 if hv100 and hv100 > 0 else np.nan

    # --- Volumen
    f["rvol"] = _safe(row["f_rvol"])

    # --- Estructura (solo swings confirmados)
    highs, lows = _confirmed_swings(df, i)

    if len(highs) >= 2 and len(lows) >= 2:
        lh, ph = _safe(highs["High"].iloc[-1]), _safe(highs["High"].iloc[-2])
        ll, pl = _safe(lows["Low"].iloc[-1]), _safe(lows["Low"].iloc[-2])
        if lh > ph and ll > pl:
            f["structure"] = 1.0      # UPTREND (HH + HL)
        elif lh < ph and ll < pl:
            f["structure"] = -1.0     # DOWNTREND (LH + LL)
        else:
            f["structure"] = 0.0      # RANGE
        f["dist_swing_high_atr"] = (lh - close) / atr_ok
        f["dist_swing_low_atr"] = (close - ll) / atr_ok
        f["bos_up"] = float(close > lh)
        f["bos_down"] = float(close < ll)

        # Posicion dentro del ultimo impulso (0 = low, 1 = high) -> zona Fibonacci
        rng = lh - ll
        f["fib_position"] = (close - ll) / rng if rng and rng > 0 else np.nan
    else:
        for k in ["structure", "dist_swing_high_atr", "dist_swing_low_atr",
                  "bos_up", "bos_down", "fib_position"]:
            f[k] = np.nan

    # --- Premium / Discount (rango de 50 velas)
    start = max(0, i - 49)
    hi50 = _safe(df["High"].iloc[start: i + 1].max())
    lo50 = _safe(df["Low"].iloc[start: i + 1].min())
    f["range50_position"] = (close - lo50) / (hi50 - lo50) if hi50 > lo50 else np.nan

    # --- Calendario
    if "Date" in df.columns:
        ts = pd.Timestamp(row["Date"])
        f["day_of_week"] = float(ts.dayofweek)
        f["hour"] = float(ts.hour)
    else:
        f["day_of_week"] = np.nan
        f["hour"] = np.nan

    return {k: (None if (isinstance(v, float) and not np.isfinite(v)) else round(float(v), 6))
            for k, v in f.items()}


FEATURE_COLUMNS = None


def feature_columns():
    """Lista ordenada de nombres de features (se calcula con datos dummy)."""
    global FEATURE_COLUMNS
    if FEATURE_COLUMNS is None:
        n = 260
        idx = pd.date_range("2020-01-01", periods=n, freq="D")
        base = 100 + np.cumsum(np.sin(np.arange(n) / 7.0))
        dummy = pd.DataFrame({
            "Date": idx, "Open": base, "High": base + 1, "Low": base - 1,
            "Close": base, "Volume": 1000.0,
        })
        FEATURE_COLUMNS = list(feature_row(add_indicators(dummy), n - 1).keys())
    return FEATURE_COLUMNS


def index_at_or_before(df, when):
    """
    Posicion de la ultima vela CERRADA en o antes de `when`.
    Para velas diarias, una entrada a las 14:00 del dia D usa la vela D-1
    (la vela D aun no ha cerrado).
    """

    when = pd.Timestamp(when)
    if when.tzinfo is not None:
        when = when.tz_convert("UTC").tz_localize(None)

    dates = pd.to_datetime(df["Date"])
    if len(dates) < 2:
        return None

    bar = (dates.diff().median())
    closes = dates + bar  # momento en que cierra cada vela

    mask = closes <= when
    if not mask.any():
        return None
    return int(np.flatnonzero(mask.values)[-1])


def features_at(df_with_indicators, when):
    i = index_at_or_before(df_with_indicators, when)
    if i is None:
        return None, None
    return i, feature_row(df_with_indicators, i)
