"""
Base de datos SQLite de la bitacora (storage/quantsignal.db).

Tablas:
  signals       -> cada analisis que hace el sistema (snapshot completo)
  trades        -> cada operacion (manual, paper, real, importada)
  trade_events  -> historial INMUTABLE de todo lo que le pasa a una operacion,
                   encadenado con hashes SHA-256 (si alguien edita un registro
                   a mano, la verificacion lo detecta)
  meta          -> version de esquema y banderas de migracion
"""

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS signals (
    id                 TEXT PRIMARY KEY,
    created_at         TEXT NOT NULL,
    source             TEXT NOT NULL DEFAULT 'ANALYZER',
    symbol             TEXT NOT NULL,
    interval           TEXT,
    candle_time        TEXT,
    signal             TEXT,
    direction          TEXT,
    score              REAL,
    confluence_score   REAL,
    probability        TEXT,
    model_probability  REAL,
    factors            TEXT,
    entry              REAL,
    stop               REAL,
    tp1                REAL,
    tp2                REAL,
    tp3                REAL,
    rr                 REAL,
    context            TEXT,
    backtest           TEXT,
    features           TEXT,
    feature_version    TEXT,
    engine_version     TEXT,
    data_hash          TEXT,
    outcome            TEXT,
    outcome_r          REAL,
    outcome_bars       INTEGER,
    outcome_mae_r      REAL,
    outcome_mfe_r      REAL,
    outcome_checked_at TEXT
);

CREATE INDEX IF NOT EXISTS ix_signals_symbol ON signals(symbol, created_at);

CREATE TABLE IF NOT EXISTS trades (
    id               TEXT PRIMARY KEY,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    source           TEXT NOT NULL,
    signal_id        TEXT REFERENCES signals(id),
    symbol           TEXT NOT NULL,
    interval         TEXT,
    direction        TEXT NOT NULL,
    status           TEXT NOT NULL,

    entry_time       TEXT,
    entry_price      REAL,
    stop_initial     REAL,
    stop_current     REAL,
    take_profit      REAL,
    quantity         REAL,
    remaining_qty    REAL,
    risk_amount      REAL,
    account_size     REAL,
    fees             REAL DEFAULT 0,
    realized_pnl     REAL DEFAULT 0,

    exit_time        TEXT,
    exit_price       REAL,
    exit_reason      TEXT,
    pnl              REAL,
    pnl_pct          REAL,
    r_multiple       REAL,
    mae_r            REAL,
    mfe_r            REAL,
    holding_hours    REAL,

    setup            TEXT,
    timeframes       TEXT,
    rationale        TEXT,
    confidence       INTEGER,
    emotion_entry    TEXT,
    emotion_exit     TEXT,
    followed_plan    INTEGER,
    mistakes         TEXT,
    tags             TEXT,
    lessons          TEXT,
    screenshot       TEXT,
    notes            TEXT,
    broker_ref       TEXT,

    features         TEXT,
    feature_version  TEXT,
    features_status  TEXT
);

CREATE INDEX IF NOT EXISTS ix_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS ix_trades_symbol ON trades(symbol, entry_time);
CREATE UNIQUE INDEX IF NOT EXISTS ux_trades_broker_ref
    ON trades(broker_ref) WHERE broker_ref IS NOT NULL;

CREATE TABLE IF NOT EXISTS trade_events (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    id         TEXT NOT NULL UNIQUE,
    trade_id   TEXT NOT NULL REFERENCES trades(id),
    ts         TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor      TEXT NOT NULL,
    payload    TEXT NOT NULL,
    prev_hash  TEXT NOT NULL,
    hash       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_events_trade ON trade_events(trade_id, seq);

-- Los eventos son de solo-agregar: se bloquean UPDATE y DELETE.
CREATE TRIGGER IF NOT EXISTS trg_events_no_update
BEFORE UPDATE ON trade_events
BEGIN
    SELECT RAISE(ABORT, 'trade_events es inmutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_events_no_delete
BEFORE DELETE ON trade_events
BEGIN
    SELECT RAISE(ABORT, 'trade_events es inmutable');
END;
"""


def connect(db_path):

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    conn.executescript(SCHEMA)

    conn.execute(
        "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()

    return conn
