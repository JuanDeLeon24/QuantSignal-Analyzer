import sqlite3

import pytest

from journal.repository import JournalError


def test_open_close_long_r_multiple(journal):
    tid = journal.open_trade("btc-usd", "LONG", 100, 95, quantity=2, take_profit=110,
                             entry_time="2026-01-05 10:00", setup="Pullback a EMA",
                             confidence=4, emotion_entry="Calmado", tags="a,b")
    t = journal.get_trade(tid)
    assert t["symbol"] == "BTC-USD"
    assert t["risk_amount"] == pytest.approx(10)
    # 10:00 Bogota = 15:00 UTC
    assert t["entry_time"] == "2026-01-05T15:00:00"
    assert t["tags"] == ["a", "b"]

    journal.close_trade(tid, 110, "2026-01-06 10:00", "TP", fees=1,
                        followed_plan=True, mistakes=["Entrada tardia"])
    t = journal.get_trade(tid)
    assert t["status"] == "CLOSED"
    assert t["pnl"] == pytest.approx(19)          # (110-100)*2 - 1
    assert t["r_multiple"] == pytest.approx(1.9)
    assert t["holding_hours"] == pytest.approx(24)
    assert t["mistakes"] == ["Entrada tardia"]
    assert t["followed_plan"] == 1


def test_short_with_partial_and_risk_sizing(journal):
    tid = journal.open_trade("SPY", "SHORT", 500, 510, risk_amount=100)
    t = journal.get_trade(tid)
    assert t["quantity"] == pytest.approx(10)
    journal.partial_close(tid, 5, 490)             # +50
    journal.update_stop(tid, 500, "breakeven")
    journal.close_trade(tid, 480)                  # +100
    t = journal.get_trade(tid)
    assert t["pnl"] == pytest.approx(150)
    assert t["r_multiple"] == pytest.approx(1.5)   # riesgo inicial = 100
    types = list(journal.get_events(tid)["event_type"])
    assert types == ["OPEN", "PARTIAL_CLOSE", "MOVE_STOP", "CLOSE"]


def test_validations(journal):
    with pytest.raises(JournalError):
        journal.open_trade("X", "LONG", 100, 101, quantity=1)      # stop arriba
    with pytest.raises(JournalError):
        journal.open_trade("X", "SHORT", 100, 99, quantity=1)      # stop abajo
    with pytest.raises(JournalError):
        journal.open_trade("X", "LONG", 100, 95)                   # sin tamano
    with pytest.raises(JournalError):
        journal.open_trade("X", "LONG", 100, 95, quantity=1, hacker="x")
    tid = journal.open_trade("X", "LONG", 100, 95, quantity=1)
    journal.close_trade(tid, 101)
    with pytest.raises(JournalError):
        journal.close_trade(tid, 102)                              # ya cerrada


def test_widened_stop_is_flagged(journal):
    tid = journal.open_trade("X", "LONG", 100, 95, quantity=1)
    journal.update_stop(tid, 90, "le di mas espacio")
    ev = journal.get_events(tid).iloc[-1]
    assert ev["payload"]["widened_risk"] is True
    assert ev["payload"]["changes"]["stop_current"] == {"before": 95.0, "after": 90.0}


def test_hash_chain_detects_tampering(journal):
    tid = journal.open_trade("X", "LONG", 100, 95, quantity=1)
    journal.add_note(tid, "todo bien")
    journal.close_trade(tid, 105)
    assert journal.verify_integrity()["ok"]

    # Los triggers impiden editar o borrar eventos
    with pytest.raises(sqlite3.DatabaseError):
        journal.conn.execute("UPDATE trade_events SET payload='{}' WHERE seq=2")
    with pytest.raises(sqlite3.DatabaseError):
        journal.conn.execute("DELETE FROM trade_events WHERE seq=2")

    # Aun si alguien quita el trigger y edita, la cadena lo detecta
    journal.conn.execute("DROP TRIGGER trg_events_no_update")
    journal.conn.execute("""UPDATE trade_events SET payload='{"text": "otra cosa"}' WHERE seq=2""")
    res = journal.verify_integrity()
    assert not res["ok"] and res["broken_at"] == 2


def test_import_csv_dedup(journal, tmp_path):
    p = tmp_path / "broker.csv"
    p.write_text(
        "ticket,symbol,side,entry_price,stop,qty,exit_price,open_time,close_time\n"
        "A1,ETH-USD,BUY,2000,1900,1,2200,2026-02-01 09:00,2026-02-03 09:00\n"
        "A2,ETH-USD,SELL,2100,2200,1,,2026-02-05 09:00,\n"
        "A3,ETH-USD,BUY,2000,2100,1,,2026-02-05 09:00,\n",
        encoding="utf-8",
    )
    r = journal.import_trades_csv(p)
    assert r["imported"] == 2 and len(r["errors"]) == 1
    r2 = journal.import_trades_csv(p)
    assert r2["imported"] == 0 and r2["skipped"] == 2
    closed = journal.list_trades(status="CLOSED")
    assert closed["r_multiple"].iloc[0] == pytest.approx(2.0)


def test_legacy_migration(journal, tmp_path):
    (tmp_path / "trade_journal.csv").write_text(
        "fecha,activo,senal,probabilidad,entrada,stop,tp1,tp2,tp3,rr\n"
        "2026-09-18 14:48:38.801787,BTC-USD,LONG,MUY ALTA,81293.1,73791.8,88794.4,92545.1,100046.4,2.5\n",
        encoding="utf-8",
    )
    assert journal.migrate_legacy_csv(tmp_path) == 1
    assert journal.migrate_legacy_csv(tmp_path) == 0   # solo una vez
    s = journal.list_signals()
    assert s["source"].iloc[0] == "LEGACY_CSV" and s["direction"].iloc[0] == "LONG"
