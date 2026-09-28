"""
Paper trading sobre la bitacora (antes usaba trades.csv).
Cada operacion virtual queda vinculada a la senal que la origino.
"""

from config import settings
from journal.repository import TradeJournal
from strategy.position_size import calculate_position_size
from strategy.risk_manager import signal_direction


def trade_exists(journal, symbol, direction):
    open_ = journal.list_trades(status=["OPEN", "PLANNED"], source="PAPER", symbol=symbol)
    return len(open_[open_["direction"] == direction]) > 0


def open_virtual_trade(symbol, signal, trade_plan, signal_id=None, journal=None, interval=None):

    direction = signal_direction(signal)

    if direction == "NONE":
        print("\n⚠ La senal es ESPERAR: no se abre operacion virtual")
        return None

    own = journal is None
    journal = journal or TradeJournal()

    try:
        if trade_exists(journal, symbol, direction):
            print("\n⚠ Ya existe una operacion virtual abierta para este activo")
            return None

        pos = calculate_position_size(
            settings.ACCOUNT_SIZE, settings.RISK_PERCENT,
            trade_plan["entry"], trade_plan["stop"],
        )

        trade_id = journal.open_trade(
            symbol=symbol,
            direction=direction,
            entry_price=trade_plan["entry"],
            stop=trade_plan["stop"],
            quantity=pos["position_size"],
            take_profit=trade_plan["tp2"],
            source="PAPER",
            signal_id=signal_id,
            interval=interval or settings.INTERVAL,
            actor="system",
            setup="Senal automatica",
            rationale=f"Senal {signal}",
        )

        print(f"\n✅ Operacion virtual creada -> ID {trade_id[:8]}")
        return trade_id

    finally:
        if own:
            journal.close()
