"""
Monitor de operaciones de paper trading: revisa las velas desde la
entrada y cierra por stop o take profit (criterio conservador: si una
vela toca ambos, cuenta el stop).
"""

import pandas as pd

from journal.enrichment import _fetch, BAR_DURATION
from ml.labeling import excursions


def update_paper_trades(journal, loader=None, log=print):

    if loader is None:
        from data.data_loader import load_data as loader

    open_ = journal.list_trades(status="OPEN", source="PAPER")
    closed = 0

    for _, t in open_.iterrows():

        interval = t["interval"] or "1d"
        entry = pd.Timestamp(t["entry_time"])
        bar = BAR_DURATION.get(interval, pd.Timedelta(days=1))

        try:
            df = _fetch(loader, t["symbol"], interval,
                        (entry - bar * 3).strftime("%Y-%m-%d"),
                        (pd.Timestamp.now("UTC").tz_localize(None) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
        except Exception as e:  # noqa: BLE001
            log(f"  {t['symbol']}: sin datos ({e})")
            continue

        dates = pd.to_datetime(df["Date"])
        # solo velas que abren despues de la entrada
        future = df[dates >= entry.floor("D") + bar if interval in ("1d", "1wk") else dates > entry]

        long = t["direction"] == "LONG"
        stop = t["stop_current"]
        tp = t["take_profit"]

        for _, b in future.iterrows():
            hit_stop = b["Low"] <= stop if long else b["High"] >= stop
            hit_tp = tp is not None and not pd.isna(tp) and (b["High"] >= tp if long else b["Low"] <= tp)
            if hit_stop or hit_tp:
                price = stop if hit_stop else tp
                reason = "SL" if hit_stop else "TP"
                between = future[pd.to_datetime(future["Date"]) <= b["Date"]]
                mae, mfe = excursions(between, t["direction"], t["entry_price"], t["stop_initial"])
                journal.close_trade(t["id"], price, exit_time=pd.Timestamp(b["Date"]).tz_localize("UTC"),
                                    exit_reason=reason, actor="system", mae_r=mae, mfe_r=mfe)
                log(f"  {t['symbol']} {t['direction']} cerrada por {reason} @ {price:.2f}")
                closed += 1
                break

    return closed
