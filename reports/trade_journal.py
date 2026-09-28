"""
Compatibilidad: antes escribia trade_journal.csv. Ahora cada analisis se
guarda como senal en la bitacora SQLite (storage/quantsignal.db).
"""

from journal.repository import TradeJournal


def save_trade_journal(analysis, journal=None):
    own = journal is None
    journal = journal or TradeJournal()
    try:
        sid = journal.log_signal(analysis)
        print(f"\n✅ Senal registrada en la bitacora -> {sid[:8]}")
        return sid
    finally:
        if own:
            journal.close()
