"""
Cache local de precios (storage/cache/*.csv).

Con 50 activos, descargar todo en cada analisis seria lento y Yahoo puede
limitar las peticiones. Aqui:
  - `prefetch` descarga en LOTES (una sola peticion para muchos tickers).
  - `get_data` usa el archivo local si tiene menos de CACHE_MAX_AGE_HOURS.
  - La vela en curso se descarta al LEER (el archivo guarda los datos crudos).
"""

import time
from pathlib import Path

import pandas as pd

from config import settings
from data.data_loader import drop_incomplete, normalize_ohlcv


def _safe(symbol):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in symbol)


def cache_path(symbol, interval=None, period=None):
    interval = interval or settings.INTERVAL
    period = period or settings.PERIOD
    return Path(settings.CACHE_DIR) / f"{_safe(symbol)}_{interval}_{period}.csv"


def is_fresh(path, max_age_hours=None):
    max_age_hours = settings.CACHE_MAX_AGE_HOURS if max_age_hours is None else max_age_hours
    return path.exists() and (time.time() - path.stat().st_mtime) < max_age_hours * 3600


def _read(path):
    df = pd.read_csv(path, parse_dates=["Date"])
    return df


def _finish(df, interval):
    if settings.DROP_INCOMPLETE_CANDLE:
        df = drop_incomplete(df, interval)
    return df


def get_data(symbol, period=None, interval=None, force=False, loader=None):
    """Datos de un activo usando la cache si esta fresca."""
    period = period or settings.PERIOD
    interval = interval or settings.INTERVAL
    path = cache_path(symbol, interval, period)
    if not force and is_fresh(path):
        return _finish(_read(path), interval)
    if loader is None:
        from data.data_loader import load_data as loader
    try:
        df = loader(symbol, period, interval, closed_only=False)
    except TypeError:
        df = loader(symbol, period, interval)
    except Exception:
        if path.exists():               # sin internet: usa la ultima copia
            return _finish(_read(path), interval)
        raise
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return _finish(df, interval)


def prefetch(symbols, period=None, interval=None, force=False, chunk=25, progress=None, log=print):
    """
    Descarga en lote los activos cuya cache esta vencida.
    Devuelve {"ok": [...], "failed": {...}, "cached": [...]}.
    """
    period = period or settings.PERIOD
    interval = interval or settings.INTERVAL
    Path(settings.CACHE_DIR).mkdir(parents=True, exist_ok=True)
    todo = [s for s in symbols if force or not is_fresh(cache_path(s, interval, period))]
    cached = [s for s in symbols if s not in todo]
    ok, failed = [], {}
    if not todo:
        return {"ok": ok, "failed": failed, "cached": cached}

    try:
        import yfinance as yf
    except ImportError:
        yf = None

    done = 0
    for i in range(0, len(todo), chunk):
        batch = todo[i:i + chunk]
        try:
            if yf is None:
                raise RuntimeError("yfinance no instalado")
            raw = yf.download(batch, period=period, interval=interval, auto_adjust=True,
                              progress=False, group_by="ticker", threads=True)
        except Exception as e:  # noqa: BLE001
            raw = None
            if yf is not None:
                log(f"  descarga en lote fallo ({e}); se intenta uno a uno")
        for s in batch:
            try:
                if raw is not None and isinstance(raw.columns, pd.MultiIndex) and s in raw.columns.get_level_values(0):
                    part = raw[s].dropna(how="all")
                    if len(part) == 0:
                        raise ValueError("sin datos")
                    df = normalize_ohlcv(part)
                elif raw is not None and len(batch) == 1 and len(raw):
                    df = normalize_ohlcv(raw)
                else:
                    raise KeyError(s)
                df.to_csv(cache_path(s, interval, period), index=False)
                ok.append(s)
            except Exception:  # noqa: BLE001
                try:
                    get_data(s, period, interval, force=True)
                    ok.append(s)
                except Exception as e2:  # noqa: BLE001
                    failed[s] = str(e2)[:120]
            done += 1
            if progress:
                progress(done, len(todo), s)
    return {"ok": ok, "failed": failed, "cached": cached}


def load_many(symbols, period=None, interval=None, progress=None, log=print):
    """Prefetch + lectura. Devuelve ({symbol: df}, {symbol: error})."""
    info = prefetch(symbols, period, interval, progress=progress, log=log)
    out, errors = {}, dict(info["failed"])
    for s in symbols:
        if s in errors:
            continue
        try:
            out[s] = get_data(s, period, interval)
        except Exception as e:  # noqa: BLE001
            errors[s] = str(e)[:120]
    return out, errors


def cache_status(symbols=None):
    symbols = symbols or settings.WATCHLIST
    rows = []
    for s in symbols:
        p = cache_path(s)
        rows.append({
            "activo": s,
            "en_cache": p.exists(),
            "fresco": is_fresh(p),
            "actualizado": pd.Timestamp(p.stat().st_mtime, unit="s").strftime("%Y-%m-%d %H:%M") if p.exists() else None,
        })
    return pd.DataFrame(rows)
