"""
Construccion del dataset de entrenamiento.

Combina tres fuentes con el MISMO esquema de features:

  MARKET  -> muestras historicas simuladas (LONG y SHORT cada N velas)
  SIGNAL  -> senales que genero el analizador, con su resultado real posterior
  MANUAL / PAPER / LIVE / IMPORT -> tus operaciones registradas en la bitacora

Cada fila trae `weight` (settings.SAMPLE_WEIGHTS) para que tus operaciones
pesen mas que las simuladas, y `label_win` / `r_result` como objetivos.
"""

import hashlib
import json
from datetime import datetime

import numpy as np
import pandas as pd

from config import settings
from ml.features import FEATURE_VERSION, add_indicators, feature_columns, feature_row
from ml.labeling import label_market_samples

META_COLUMNS = ["sample_id", "source", "symbol", "interval", "time", "direction"]
TARGET_COLUMNS = ["label_win", "r_result", "outcome", "weight"]
# Columnas de contexto humano (para analisis, no se usan como features del modelo)
HUMAN_COLUMNS = ["setup", "confidence", "emotion_entry", "followed_plan", "mistakes"]


def _row(source, symbol, interval, time, direction, feats, r_result, outcome, extra=None):
    r = {
        "source": source,
        "symbol": symbol,
        "interval": interval,
        "time": pd.Timestamp(time),
        "direction": direction,
        "dir_long": 1.0 if direction == "LONG" else 0.0,
    }
    for c in feature_columns():
        v = (feats or {}).get(c)
        r[c] = np.nan if v is None else float(v)
    r["r_result"] = float(r_result)
    r["label_win"] = int(r_result > 0)
    r["outcome"] = outcome
    r["weight"] = settings.SAMPLE_WEIGHTS.get(source, 1.0)
    if extra:
        r.update(extra)
    return r


def market_rows(symbol, df, interval="1d", stride=5, stop_atr=1.5, rr=2.0, max_bars=20):
    ind = add_indicators(df)
    rows = []
    for s in label_market_samples(ind, symbol, stride=stride, stop_atr=stop_atr,
                                  rr=rr, max_bars=max_bars):
        feats = feature_row(ind, s["index"])
        rows.append(_row("MARKET", symbol, interval, s["time"], s["direction"], feats,
                         s["r_result"], s["outcome"]))
    return rows


def signal_rows(journal):
    sig = journal.list_signals()
    if len(sig) == 0:
        return []
    sig = sig[
        sig["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])
        & sig["direction"].isin(["LONG", "SHORT"])
        & sig["features"].notna()
    ]
    rows = []
    for _, s in sig.iterrows():
        feats = json.loads(s["features"]) if s["features"] else {}
        if not feats:
            continue
        rows.append(_row("SIGNAL", s["symbol"], s["interval"], s["candle_time"] or s["created_at"],
                         s["direction"], feats, s["outcome_r"], s["outcome"],
                         {"ref_id": s["id"]}))
    return rows


def trade_rows(journal):
    tr = journal.list_trades(status="CLOSED")
    if len(tr) == 0:
        return []
    tr = tr[(tr["features_status"] == "OK") & tr["r_multiple"].notna()]
    rows = []
    for _, t in tr.iterrows():
        feats = json.loads(t["features"])
        outcome = "WIN" if t["r_multiple"] > 0 else "LOSS"
        rows.append(_row(
            t["source"], t["symbol"], t["interval"], t["entry_time"], t["direction"], feats,
            t["r_multiple"], outcome,
            {
                "ref_id": t["id"],
                "setup": t["setup"],
                "confidence": t["confidence"],
                "emotion_entry": t["emotion_entry"],
                "followed_plan": t["followed_plan"],
                "mistakes": t["mistakes"],
            },
        ))
    return rows


def build_dataset(journal, symbols=None, include_market=True, loader=None,
                  period=None, interval=None, stride=5, market_data=None, log=print, progress=None):
    """
    market_data: dict opcional {symbol: DataFrame OHLCV} para no descargar.
    """
    rows = []
    period = period or settings.PERIOD
    interval = interval or settings.INTERVAL

    if include_market:
        symbols = symbols or settings.WATCHLIST
        if loader is None and market_data is None:
            from data.cache import get_data, prefetch
            prefetch(symbols, period, interval, log=log)
            loader = get_data
        for k, sym in enumerate(symbols, 1):
            if progress:
                progress(k - 1, len(symbols), sym)
            try:
                df = market_data[sym] if market_data and sym in market_data else loader(sym, period, interval)
                r = market_rows(sym, df, interval=interval, stride=stride)
                rows += r
                log(f"  MARKET {sym}: {len(r)} muestras")
            except Exception as e:  # noqa: BLE001
                log(f"  MARKET {sym}: error {e}")
        if progress:
            progress(len(symbols), len(symbols), "listo")

    s = signal_rows(journal)
    t = trade_rows(journal)
    log(f"  SIGNAL: {len(s)} muestras | OPERACIONES: {len(t)} muestras")
    rows += s + t

    if not rows:
        return pd.DataFrame()

    ds = pd.DataFrame(rows).sort_values("time").reset_index(drop=True)
    ds["time"] = pd.to_datetime(ds["time"], utc=True).dt.tz_localize(None)
    ds["sample_id"] = [
        hashlib.sha1(f"{a}|{b}|{c}|{d}".encode()).hexdigest()[:12]
        for a, b, c, d in zip(ds["source"], ds["symbol"], ds["time"], ds["direction"])
    ]
    return ds


def save_dataset(ds, out_dir=None):
    out_dir = out_dir or settings.DATASETS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"dataset_{stamp}.csv"
    ds.to_csv(path, index=False)
    meta = {
        "created_at": stamp,
        "rows": int(len(ds)),
        "feature_version": FEATURE_VERSION,
        "features": feature_columns(),
        "by_source": ds["source"].value_counts().to_dict(),
        "win_rate_by_source": ds.groupby("source")["label_win"].mean().round(4).to_dict(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    meta_path = path.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return path, meta
