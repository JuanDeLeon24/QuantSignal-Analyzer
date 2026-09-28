"""
Enriquecimiento automatico de registros.

  enrich_trade      -> a una operacion (manual o no) le calcula las MISMAS
                       features tecnicas que ve el analizador en la vela de
                       entrada, y su MAE/MFE si ya esta cerrada.
  enrich_pending    -> hace lo anterior con todas las pendientes.
  evaluate_signals  -> revisa senales pasadas y registra que habria pasado
                       (WIN/LOSS/TIMEOUT) aunque no las hayas operado.
"""

from datetime import timedelta

import pandas as pd

from config import settings
from ml.features import FEATURE_VERSION, add_indicators, feature_row, index_at_or_before
from ml.labeling import excursions, simulate_outcome

BAR_DURATION = {
    "1m": timedelta(minutes=1), "5m": timedelta(minutes=5), "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30), "1h": timedelta(hours=1), "4h": timedelta(hours=4),
    "1d": timedelta(days=1), "1wk": timedelta(weeks=1),
}

# Historia maxima que Yahoo entrega por intervalo
MAX_HISTORY = {
    "1m": timedelta(days=7), "5m": timedelta(days=59), "15m": timedelta(days=59),
    "30m": timedelta(days=59), "1h": timedelta(days=729), "4h": timedelta(days=729),
}

LOOKBACK_BARS = 320


def _default_loader():
    from data.data_loader import load_data
    return load_data


def _fetch(loader, symbol, interval, start, end):
    """Descarga velas; 4h se construye a partir de 1h."""
    yf_interval = "1h" if interval == "4h" else interval
    df = loader(symbol, interval=yf_interval, start=start, end=end)
    if interval == "4h":
        df = (
            df.set_index("Date")
            .resample("4h")
            .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
            .dropna()
            .reset_index()
        )
    return df


def _window(interval, start_time, end_time):
    bar = BAR_DURATION.get(interval, timedelta(days=1))
    # los fines de semana en acciones "comen" barras: margen x1.6
    start = pd.Timestamp(start_time) - bar * int(LOOKBACK_BARS * 1.6)
    end = pd.Timestamp(end_time) + bar * 3
    if interval in MAX_HISTORY:
        earliest = pd.Timestamp.now("UTC").tz_localize(None) - MAX_HISTORY[interval]
        start = max(start, earliest)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def enrich_trade(journal, trade_id, loader=None, df=None):
    """
    Calcula features en la entrada y MAE/MFE. Devuelve el estado final.
    Se puede pasar `df` (OHLCV) para no descargar.
    """
    loader = loader or _default_loader()
    t = journal.get_trade(trade_id)
    interval = t.get("interval") or "1d"

    entry_time = pd.Timestamp(t["entry_time"])
    end_time = pd.Timestamp(t["exit_time"]) if t.get("exit_time") else pd.Timestamp.now("UTC").tz_localize(None)

    try:
        if df is None:
            start, end = _window(interval, entry_time, end_time)
            df = _fetch(loader, t["symbol"], interval, start, end)
        ind = add_indicators(df)

        i = index_at_or_before(ind, entry_time)
        if i is None or i < 50:
            journal.set_features(t["id"], None, status="NO_DATA",
                                 detail="No hay suficientes velas antes de la entrada")
            return "NO_DATA"

        feats = feature_row(ind, i)
        feats["candle_time"] = str(ind["Date"].iloc[i])

        mae = mfe = None
        if t.get("exit_time"):
            dates = pd.to_datetime(ind["Date"])
            between = ind[(dates > ind["Date"].iloc[i]) & (dates <= end_time)]
            mae, mfe = excursions(between, t["direction"], t["entry_price"], t["stop_initial"])

        journal.set_features(t["id"], feats, status="OK", mae_r=mae, mfe_r=mfe,
                             feature_version=FEATURE_VERSION)
        return "OK"

    except Exception as e:  # noqa: BLE001
        journal.set_features(t["id"], None, status="ERROR", detail=str(e)[:300])
        return "ERROR"


def enrich_pending(journal, loader=None, include_closed_without_excursion=True):
    trades = journal.list_trades()
    if len(trades) == 0:
        return {}
    todo = trades[
        trades["features_status"].isin(["PENDING", "ERROR"])
        | (
            include_closed_without_excursion
            & (trades["status"] == "CLOSED")
            & trades["mae_r"].isna()
            & (trades["features_status"] == "OK")
        )
    ]
    todo = todo[todo["status"] != "CANCELLED"]
    results = {}
    for tid in todo["id"]:
        results[tid] = enrich_trade(journal, tid, loader=loader)
    return results


def evaluate_signals(journal, loader=None, max_bars=None, target="tp2"):
    """
    Evalua las senales LONG/SHORT pendientes: simula stop vs objetivo
    en las velas siguientes. Las que aun no tienen suficientes velas
    quedan en 'OPEN' y se reevaluan en la proxima ejecucion.
    """
    loader = loader or _default_loader()
    max_bars = max_bars or settings.OUTCOME_MAX_BARS
    pending = journal.list_signals(pending_outcome=True)
    summary = {"evaluated": 0, "open": 0, "errors": 0}
    if len(pending) == 0:
        return summary

    pending = pending[pending["entry"].notna() & pending["stop"].notna() & pending[target].notna()]

    for (symbol, interval), group in pending.groupby(["symbol", "interval"], dropna=False):
        interval = interval or "1d"
        first = pd.to_datetime(group["created_at"]).min()
        try:
            start = (first - BAR_DURATION.get(interval, timedelta(days=1)) * 3).strftime("%Y-%m-%d")
            end = (pd.Timestamp.now("UTC").tz_localize(None) + timedelta(days=1)).strftime("%Y-%m-%d")
            df = _fetch(loader, symbol, interval, start, end)
        except Exception:  # noqa: BLE001
            summary["errors"] += len(group)
            continue

        dates = pd.to_datetime(df["Date"])
        for _, s in group.iterrows():
            # El resultado se mide desde la vela SIGUIENTE a la usada en el analisis
            if s.get("candle_time") and str(s["candle_time"]) not in ("None", "nan"):
                ref = pd.Timestamp(s["candle_time"])
            else:
                created = pd.Timestamp(s["created_at"])
                ref = dates[dates <= created].max() if (dates <= created).any() else created
            future = df[dates > ref]
            out = simulate_outcome(future, s["direction"], s["entry"], s["stop"], s[target], max_bars)
            if out is None:
                continue
            journal.set_signal_outcome(s["id"], out)
            summary["open" if out["outcome"] == "OPEN" else "evaluated"] += 1

    return summary
