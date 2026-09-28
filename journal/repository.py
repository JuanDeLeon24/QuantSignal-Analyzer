"""
TradeJournal: API unica para registrar y consultar senales y operaciones
con trazabilidad completa.

Cada cambio en una operacion genera un evento inmutable en `trade_events`
con: quien lo hizo (actor), cuando, que cambio (antes/despues) y un hash
encadenado al evento anterior.
"""

import csv
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import settings
from journal.db import connect

GENESIS_HASH = "0" * 64

DIRECTIONS = ("LONG", "SHORT")
SOURCES = ("MANUAL", "PAPER", "LIVE", "IMPORT")
STATUSES = ("PLANNED", "OPEN", "CLOSED", "CANCELLED")

# Campos descriptivos que el usuario puede editar despues de abrir
EDITABLE_FIELDS = {
    "take_profit", "setup", "timeframes", "rationale", "confidence",
    "emotion_entry", "emotion_exit", "followed_plan", "mistakes", "tags",
    "lessons", "screenshot", "notes", "interval", "broker_ref",
}

# Etiquetas sugeridas (puedes usar las tuyas)
SETUPS = [
    "Pullback a EMA", "Ruptura (BOS)", "Cambio de caracter (CHOCH)",
    "Retroceso Fibonacci", "Order Block", "Fair Value Gap",
    "Barrido de liquidez", "Rango / reversion", "Noticia / fundamental", "Otro",
]
EMOTIONS = [
    "Calmado", "Confiado", "Ansioso", "FOMO", "Miedo", "Euforia",
    "Venganza", "Aburrido", "Cansado", "Dudoso",
]
MISTAKES = [
    "Entrada anticipada", "Entrada tardia", "Sin stop", "Movi el stop en contra",
    "Cierre anticipado", "Sobreapalancado", "Fuera del plan", "Ignore temporalidad mayor",
    "Opere contra tendencia", "Opere en noticia", "Sobreoperacion",
]
EXIT_REASONS = ["TP", "SL", "TRAILING", "MANUAL", "TIMEOUT", "BREAKEVEN", "INVALIDACION"]


# =========================================================
# UTILIDADES
# =========================================================

def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")


def to_utc_iso(value, assume_tz=None):
    """
    Convierte fechas a ISO UTC. Si la fecha no tiene zona horaria se asume
    la zona local configurada (LOCAL_TZ), que es como la escribe el usuario.
    """
    if value is None or value == "":
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize(assume_tz or settings.LOCAL_TZ)
    return ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%S")


def utc_to_local(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(settings.LOCAL_TZ)


def _dumps(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=_json_default)


def _json_default(o):
    if isinstance(o, (pd.Timestamp, datetime)):
        return o.isoformat()
    try:
        import numpy as np
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return None if not np.isfinite(o) else float(o)
        if isinstance(o, np.bool_):
            return bool(o)
    except ImportError:
        pass
    return str(o)


def _hash(prev_hash, event_id, trade_id, ts, event_type, actor, payload_json):
    raw = "|".join([prev_hash, event_id, trade_id, ts, event_type, actor, payload_json])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _as_list(value):
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if str(v).strip()]
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except (TypeError, ValueError):
        pass
    return [s.strip() for s in str(value).split(",") if s.strip()]


class JournalError(ValueError):
    pass


# =========================================================
# JOURNAL
# =========================================================

class TradeJournal:

    def __init__(self, db_path=None):
        self.db_path = Path(db_path or settings.DB_PATH)
        self.conn = connect(self.db_path)

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -----------------------------------------------------
    # EVENTOS (auditoria)
    # -----------------------------------------------------

    def _last_hash(self):
        row = self.conn.execute(
            "SELECT hash FROM trade_events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return row["hash"] if row else GENESIS_HASH

    def _append_event(self, trade_id, event_type, payload, actor="user"):
        event_id = str(uuid.uuid4())
        ts = utcnow()
        payload_json = _dumps(payload)
        prev = self._last_hash()
        h = _hash(prev, event_id, trade_id, ts, event_type, actor, payload_json)
        self.conn.execute(
            """INSERT INTO trade_events(id, trade_id, ts, event_type, actor, payload, prev_hash, hash)
               VALUES (?,?,?,?,?,?,?,?)""",
            (event_id, trade_id, ts, event_type, actor, payload_json, prev, h),
        )
        return event_id

    def verify_integrity(self):
        """
        Recorre toda la cadena de eventos y recalcula los hashes.
        Devuelve {"ok": bool, "checked": n, "broken_at": seq|None, "detail": str}
        """
        prev = GENESIS_HASH
        n = 0
        for row in self.conn.execute("SELECT * FROM trade_events ORDER BY seq"):
            n += 1
            if row["prev_hash"] != prev:
                return {"ok": False, "checked": n, "broken_at": row["seq"],
                        "detail": "Falta un evento o se altero el orden"}
            h = _hash(prev, row["id"], row["trade_id"], row["ts"], row["event_type"],
                      row["actor"], row["payload"])
            if h != row["hash"]:
                return {"ok": False, "checked": n, "broken_at": row["seq"],
                        "detail": "El contenido del evento fue modificado"}
            prev = row["hash"]
        return {"ok": True, "checked": n, "broken_at": None, "detail": "Cadena integra"}

    def get_events(self, trade_id=None):
        q = "SELECT * FROM trade_events"
        args = ()
        if trade_id:
            q += " WHERE trade_id = ?"
            args = (trade_id,)
        q += " ORDER BY seq"
        df = pd.read_sql_query(q, self.conn, params=args)
        if len(df):
            df["payload"] = df["payload"].apply(json.loads)
        return df

    # -----------------------------------------------------
    # SENALES
    # -----------------------------------------------------

    def log_signal(self, analysis, source="ANALYZER"):
        """
        Guarda el snapshot completo de un analisis (ver core/analyzer.py).
        """
        sid = analysis.get("signal_id") or str(uuid.uuid4())
        plan = analysis.get("trade_plan", {})
        self.conn.execute(
            """INSERT INTO signals(id, created_at, source, symbol, interval, candle_time, signal,
                   direction, score, confluence_score, probability, model_probability, factors,
                   entry, stop, tp1, tp2, tp3, rr, context, backtest, features, feature_version,
                   engine_version, data_hash)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                sid, analysis.get("created_at") or utcnow(), source,
                analysis["symbol"], analysis.get("interval"),
                str(analysis.get("candle_time")) if analysis.get("candle_time") is not None else None,
                analysis.get("signal"), plan.get("direction"),
                analysis.get("score"), analysis.get("confluence_score"),
                analysis.get("probability"), analysis.get("model_probability"),
                _dumps(analysis.get("factors", [])),
                plan.get("entry"), plan.get("stop"), plan.get("tp1"), plan.get("tp2"),
                plan.get("tp3"), plan.get("rr"),
                _dumps(analysis.get("context", {})),
                _dumps(analysis.get("backtest_summary", {})),
                _dumps(analysis.get("features", {})),
                analysis.get("feature_version"),
                analysis.get("engine_version", settings.ENGINE_VERSION),
                analysis.get("data_hash"),
            ),
        )
        self.conn.commit()
        return sid

    def list_signals(self, symbol=None, pending_outcome=False, limit=None):
        q = "SELECT * FROM signals WHERE 1=1"
        args = []
        if symbol:
            q += " AND symbol = ?"
            args.append(symbol)
        if pending_outcome:
            q += " AND (outcome IS NULL OR outcome = 'OPEN') AND direction IN ('LONG','SHORT')"
        q += " ORDER BY created_at DESC"
        if limit:
            q += f" LIMIT {int(limit)}"
        return pd.read_sql_query(q, self.conn, params=args)

    def get_signal(self, signal_id):
        row = self.conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
        return dict(row) if row else None

    def set_signal_outcome(self, signal_id, outcome):
        self.conn.execute(
            """UPDATE signals SET outcome=?, outcome_r=?, outcome_bars=?, outcome_mae_r=?,
                   outcome_mfe_r=?, outcome_checked_at=? WHERE id=?""",
            (outcome["outcome"], outcome["r_result"], outcome["bars"], outcome.get("mae_r"),
             outcome.get("mfe_r"), utcnow(), signal_id),
        )
        self.conn.commit()

    # -----------------------------------------------------
    # OPERACIONES
    # -----------------------------------------------------

    def open_trade(
        self,
        symbol,
        direction,
        entry_price,
        stop,
        quantity=None,
        risk_amount=None,
        take_profit=None,
        entry_time=None,
        source="MANUAL",
        signal_id=None,
        interval="1d",
        status="OPEN",
        actor="user",
        account_size=None,
        fees=0.0,
        **meta,
    ):
        direction = str(direction).upper()
        source = str(source).upper()
        status = str(status).upper()

        if direction not in DIRECTIONS:
            raise JournalError("La direccion debe ser LONG o SHORT")
        if source not in SOURCES:
            raise JournalError(f"Fuente invalida: {source}")
        if status not in ("PLANNED", "OPEN"):
            raise JournalError("Una operacion nueva debe estar PLANNED u OPEN")

        entry_price = float(entry_price)
        stop = float(stop)

        if entry_price <= 0 or stop <= 0:
            raise JournalError("Precio de entrada y stop deben ser positivos")
        if direction == "LONG" and stop >= entry_price:
            raise JournalError("En un LONG el stop debe estar por DEBAJO de la entrada")
        if direction == "SHORT" and stop <= entry_price:
            raise JournalError("En un SHORT el stop debe estar por ENCIMA de la entrada")

        if take_profit not in (None, ""):
            take_profit = float(take_profit)
            if direction == "LONG" and take_profit <= entry_price:
                raise JournalError("En un LONG el take profit debe estar por ENCIMA de la entrada")
            if direction == "SHORT" and take_profit >= entry_price:
                raise JournalError("En un SHORT el take profit debe estar por DEBAJO de la entrada")
        else:
            take_profit = None

        risk_per_unit = abs(entry_price - stop)

        if quantity in (None, "", 0) and risk_amount in (None, "", 0):
            raise JournalError("Indica la cantidad o el monto que arriesgas")
        if quantity in (None, "", 0):
            quantity = float(risk_amount) / risk_per_unit
        quantity = float(quantity)
        if quantity <= 0:
            raise JournalError("La cantidad debe ser positiva")
        risk_amount = quantity * risk_per_unit

        unknown = set(meta) - EDITABLE_FIELDS
        if unknown:
            raise JournalError(f"Campos desconocidos: {sorted(unknown)}")

        if signal_id and not self.get_signal(signal_id):
            raise JournalError(f"No existe la senal {signal_id}")

        for k in ("mistakes", "tags"):
            if k in meta:
                meta[k] = _dumps(_as_list(meta[k]))
        if "followed_plan" in meta and meta["followed_plan"] is not None:
            meta["followed_plan"] = int(bool(meta["followed_plan"]))

        now = utcnow()
        trade_id = str(uuid.uuid4())

        record = {
            "id": trade_id,
            "created_at": now,
            "updated_at": now,
            "source": source,
            "signal_id": signal_id,
            "symbol": symbol.upper().strip(),
            "interval": interval,
            "direction": direction,
            "status": status,
            "entry_time": to_utc_iso(entry_time) if entry_time else now,
            "entry_price": entry_price,
            "stop_initial": stop,
            "stop_current": stop,
            "take_profit": take_profit,
            "quantity": quantity,
            "remaining_qty": quantity,
            "risk_amount": risk_amount,
            "account_size": account_size if account_size is not None else settings.ACCOUNT_SIZE,
            "fees": float(fees or 0),
            "realized_pnl": 0.0,
            "features_status": "PENDING",
            **meta,
        }

        cols = ", ".join(record)
        marks = ", ".join("?" for _ in record)
        with self.conn:
            self.conn.execute(f"INSERT INTO trades({cols}) VALUES ({marks})", tuple(record.values()))
            self._append_event(trade_id, "OPEN" if status == "OPEN" else "PLAN", record, actor)

        return trade_id

    def get_trade(self, trade_id):
        row = self.conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        if not row:
            # permite usar solo el prefijo del id (8 caracteres)
            rows = self.conn.execute(
                "SELECT * FROM trades WHERE id LIKE ?", (f"{trade_id}%",)
            ).fetchall()
            if len(rows) == 1:
                row = rows[0]
        if not row:
            raise JournalError(f"No existe la operacion {trade_id}")
        t = dict(row)
        for k in ("mistakes", "tags"):
            t[k] = _as_list(t.get(k))
        t["features"] = json.loads(t["features"]) if t.get("features") else None
        return t

    def _update(self, trade_id, changes, event_type, actor, reason=None, extra=None):
        before = self.get_trade(trade_id)
        trade_id = before["id"]
        diff = {}
        for k, v in changes.items():
            old = before.get(k)
            if k in ("mistakes", "tags"):
                old = _dumps(old)
            if old != v:
                diff[k] = {"before": old, "after": v}
        payload = {"changes": diff}
        if reason:
            payload["reason"] = reason
        if extra:
            payload.update(extra)
        changes = dict(changes)
        changes["updated_at"] = utcnow()
        sets = ", ".join(f"{k} = ?" for k in changes)
        with self.conn:
            self.conn.execute(f"UPDATE trades SET {sets} WHERE id = ?", (*changes.values(), trade_id))
            self._append_event(trade_id, event_type, payload, actor)
        return trade_id

    def _require_status(self, trade, allowed):
        if trade["status"] not in allowed:
            raise JournalError(
                f"La operacion {trade['id'][:8]} esta {trade['status']}; accion no permitida"
            )

    def activate_trade(self, trade_id, entry_price=None, entry_time=None, actor="user"):
        """Pasa una operacion PLANNED a OPEN (la orden se ejecuto)."""
        t = self.get_trade(trade_id)
        self._require_status(t, ("PLANNED",))
        changes = {"status": "OPEN"}
        if entry_price:
            changes["entry_price"] = float(entry_price)
        changes["entry_time"] = to_utc_iso(entry_time) if entry_time else utcnow()
        return self._update(t["id"], changes, "ACTIVATE", actor)

    def update_stop(self, trade_id, new_stop, reason="", actor="user"):
        t = self.get_trade(trade_id)
        self._require_status(t, ("PLANNED", "OPEN"))
        new_stop = float(new_stop)
        # un stop que aumenta el riesgo inicial queda marcado
        widened = (
            (t["direction"] == "LONG" and new_stop < t["stop_current"])
            or (t["direction"] == "SHORT" and new_stop > t["stop_current"])
        )
        return self._update(
            t["id"], {"stop_current": new_stop}, "MOVE_STOP", actor, reason,
            extra={"widened_risk": widened},
        )

    def update_fields(self, trade_id, reason="", actor="user", **fields):
        unknown = set(fields) - EDITABLE_FIELDS
        if unknown:
            raise JournalError(f"Campos no editables: {sorted(unknown)}")
        for k in ("mistakes", "tags"):
            if k in fields:
                fields[k] = _dumps(_as_list(fields[k]))
        if "followed_plan" in fields and fields["followed_plan"] is not None:
            fields["followed_plan"] = int(bool(fields["followed_plan"]))
        return self._update(trade_id, fields, "EDIT", actor, reason)

    def add_note(self, trade_id, text, actor="user"):
        t = self.get_trade(trade_id)
        with self.conn:
            self._append_event(t["id"], "NOTE", {"text": text}, actor)
            self.conn.execute("UPDATE trades SET updated_at=? WHERE id=?", (utcnow(), t["id"]))

    def _pnl(self, t, qty, price):
        sign = 1 if t["direction"] == "LONG" else -1
        return sign * (float(price) - t["entry_price"]) * float(qty)

    def partial_close(self, trade_id, quantity, price, exit_time=None, reason="TP parcial",
                      fees=0.0, actor="user"):
        t = self.get_trade(trade_id)
        self._require_status(t, ("OPEN",))
        quantity = float(quantity)
        if quantity <= 0 or quantity >= t["remaining_qty"] - 1e-12:
            raise JournalError("La cantidad parcial debe ser mayor a 0 y menor a la posicion abierta")
        pnl = self._pnl(t, quantity, price) - float(fees or 0)
        changes = {
            "remaining_qty": t["remaining_qty"] - quantity,
            "realized_pnl": (t["realized_pnl"] or 0) + pnl,
            "fees": (t["fees"] or 0) + float(fees or 0),
        }
        return self._update(
            t["id"], changes, "PARTIAL_CLOSE", actor, reason,
            extra={"quantity": quantity, "price": float(price), "pnl": pnl,
                   "time": to_utc_iso(exit_time) if exit_time else utcnow()},
        )

    def close_trade(
        self,
        trade_id,
        exit_price,
        exit_time=None,
        exit_reason="MANUAL",
        fees=0.0,
        actor="user",
        mae_r=None,
        mfe_r=None,
        **review,
    ):
        """
        Cierra la posicion restante y calcula PnL, % y multiplo R.
        `review` admite: emotion_exit, followed_plan, mistakes, lessons, notes...
        """
        t = self.get_trade(trade_id)
        self._require_status(t, ("OPEN",))

        unknown = set(review) - EDITABLE_FIELDS
        if unknown:
            raise JournalError(f"Campos desconocidos: {sorted(unknown)}")

        exit_iso = to_utc_iso(exit_time) if exit_time else utcnow()
        if exit_iso < t["entry_time"]:
            raise JournalError("La fecha de salida es anterior a la de entrada")

        fees = float(fees or 0)
        last_pnl = self._pnl(t, t["remaining_qty"], exit_price) - fees
        total_pnl = (t["realized_pnl"] or 0) + last_pnl
        total_fees = (t["fees"] or 0) + fees
        initial_risk = abs(t["entry_price"] - t["stop_initial"]) * t["quantity"]
        notional = t["entry_price"] * t["quantity"]

        hours = (pd.Timestamp(exit_iso) - pd.Timestamp(t["entry_time"])).total_seconds() / 3600

        changes = {
            "status": "CLOSED",
            "exit_price": float(exit_price),
            "exit_time": exit_iso,
            "exit_reason": exit_reason,
            "remaining_qty": 0.0,
            "realized_pnl": total_pnl,
            "fees": total_fees,
            "pnl": total_pnl,
            "pnl_pct": total_pnl / notional * 100 if notional else None,
            "r_multiple": total_pnl / initial_risk if initial_risk else None,
            "holding_hours": round(hours, 2),
        }
        if mae_r is not None:
            changes["mae_r"] = mae_r
        if mfe_r is not None:
            changes["mfe_r"] = mfe_r

        for k in ("mistakes", "tags"):
            if k in review:
                review[k] = _dumps(_as_list(review[k]))
        if "followed_plan" in review and review["followed_plan"] is not None:
            review["followed_plan"] = int(bool(review["followed_plan"]))
        changes.update(review)

        return self._update(t["id"], changes, "CLOSE", actor, exit_reason)

    def cancel_trade(self, trade_id, reason="", actor="user"):
        t = self.get_trade(trade_id)
        self._require_status(t, ("PLANNED", "OPEN"))
        return self._update(t["id"], {"status": "CANCELLED"}, "CANCEL", actor, reason)

    def set_features(self, trade_id, features, status="OK", mae_r=None, mfe_r=None,
                     feature_version=None, actor="system", detail=None):
        t = self.get_trade(trade_id)
        changes = {
            "features": _dumps(features) if features is not None else None,
            "features_status": status,
            "feature_version": feature_version,
        }
        if mae_r is not None:
            changes["mae_r"] = mae_r
        if mfe_r is not None:
            changes["mfe_r"] = mfe_r
        payload = {"status": status, "n_features": len(features or {}),
                   "feature_version": feature_version, "mae_r": mae_r, "mfe_r": mfe_r}
        if detail:
            payload["detail"] = detail
        changes["updated_at"] = utcnow()
        sets = ", ".join(f"{k} = ?" for k in changes)
        with self.conn:
            self.conn.execute(f"UPDATE trades SET {sets} WHERE id = ?", (*changes.values(), t["id"]))
            self._append_event(t["id"], "FEATURES", payload, actor)

    def list_trades(self, status=None, source=None, symbol=None):
        q = "SELECT * FROM trades WHERE 1=1"
        args = []
        for col, val in (("status", status), ("source", source), ("symbol", symbol)):
            if val:
                if isinstance(val, (list, tuple)):
                    q += f" AND {col} IN ({','.join('?' for _ in val)})"
                    args.extend(val)
                else:
                    q += f" AND {col} = ?"
                    args.append(val)
        q += " ORDER BY entry_time"
        return pd.read_sql_query(q, self.conn, params=args)

    # -----------------------------------------------------
    # IMPORTAR / EXPORTAR / MIGRAR
    # -----------------------------------------------------

    IMPORT_COLUMNS = {
        # columna del CSV -> campo de la bitacora
        "symbol": "symbol", "activo": "symbol",
        "direction": "direction", "side": "direction", "senal": "direction",
        "entry_time": "entry_time", "fecha_entrada": "entry_time", "open_time": "entry_time",
        "entry_price": "entry_price", "entrada": "entry_price", "open_price": "entry_price",
        "stop": "stop", "stop_loss": "stop", "sl": "stop",
        "take_profit": "take_profit", "tp": "take_profit",
        "quantity": "quantity", "cantidad": "quantity", "qty": "quantity", "size": "quantity",
        "exit_time": "exit_time", "fecha_salida": "exit_time", "close_time": "exit_time",
        "exit_price": "exit_price", "salida": "exit_price", "close_price": "exit_price",
        "fees": "fees", "comision": "fees", "commission": "fees",
        "setup": "setup", "notes": "notes", "notas": "notes",
        "broker_ref": "broker_ref", "order_id": "broker_ref", "ticket": "broker_ref", "id": "broker_ref",
        "interval": "interval",
    }

    def import_trades_csv(self, path, actor="import"):
        """
        Importa operaciones de un CSV (export de tu broker/exchange o una hoja propia).
        Columnas minimas: symbol, direction(LONG/SHORT/BUY/SELL), entry_price, stop, quantity.
        Si trae exit_price, la operacion queda cerrada. `broker_ref` evita duplicados.
        Devuelve {"imported": n, "skipped": n, "errors": [...]}
        """
        df = pd.read_csv(path)
        df.columns = [c.strip().lower() for c in df.columns]
        df = df.rename(columns={c: self.IMPORT_COLUMNS[c] for c in df.columns if c in self.IMPORT_COLUMNS})

        imported, skipped, errors = 0, 0, []
        for n, row in df.iterrows():
            r = {k: (None if pd.isna(v) else v) for k, v in row.items()}
            try:
                d = str(r.get("direction", "")).upper()
                d = {"BUY": "LONG", "SELL": "SHORT", "COMPRA": "LONG", "VENTA": "SHORT"}.get(d, d)
                ref = str(r["broker_ref"]) if r.get("broker_ref") is not None else None
                if ref and self.conn.execute("SELECT 1 FROM trades WHERE broker_ref=?", (ref,)).fetchone():
                    skipped += 1
                    continue
                tid = self.open_trade(
                    symbol=str(r["symbol"]), direction=d, entry_price=r["entry_price"],
                    stop=r["stop"], quantity=r.get("quantity"), take_profit=r.get("take_profit"),
                    entry_time=r.get("entry_time"), source="IMPORT", actor=actor,
                    interval=r.get("interval") or "1d",
                    setup=r.get("setup"), notes=r.get("notes"), broker_ref=ref,
                )
                if r.get("exit_price") is not None:
                    self.close_trade(tid, r["exit_price"], exit_time=r.get("exit_time"),
                                     exit_reason="IMPORT", fees=r.get("fees") or 0, actor=actor)
                imported += 1
            except Exception as e:  # noqa: BLE001
                errors.append(f"fila {n + 2}: {e}")
        return {"imported": imported, "skipped": skipped, "errors": errors}

    def migrate_legacy_csv(self, base_dir=None):
        """
        Importa una sola vez el trade_journal.csv antiguo como senales LEGACY.
        """
        flag = self.conn.execute("SELECT value FROM meta WHERE key='legacy_migrated'").fetchone()
        if flag:
            return 0
        base_dir = Path(base_dir or settings.BASE_DIR)
        path = base_dir / "trade_journal.csv"
        n = 0
        if path.exists():
            with open(path, encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    try:
                        signal = row.get("senal", "")
                        direction = "LONG" if signal.startswith("LONG") else (
                            "SHORT" if signal.startswith("SHORT") else "NONE")
                        created = pd.Timestamp(row["fecha"]).tz_localize(settings.LOCAL_TZ)
                        self.log_signal({
                            "symbol": row["activo"],
                            "interval": settings.INTERVAL,
                            "created_at": created.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%S"),
                            "signal": signal,
                            "probability": row.get("probabilidad"),
                            "trade_plan": {
                                "direction": direction,
                                "entry": float(row["entrada"]), "stop": float(row["stop"]),
                                "tp1": float(row["tp1"]), "tp2": float(row["tp2"]),
                                "tp3": float(row["tp3"]), "rr": float(row["rr"]),
                            },
                            "engine_version": "1.x",
                        }, source="LEGACY_CSV")
                        n += 1
                    except (KeyError, ValueError):
                        continue
        self.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('legacy_migrated', ?)", (utcnow(),))
        self.conn.commit()
        return n

    def export_csv(self, out_dir=None):
        out_dir = Path(out_dir or settings.OUTPUT_DIR / "exports")
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        paths = {}
        for name, df in (
            ("trades", self.list_trades()),
            ("signals", self.list_signals()),
            ("events", pd.read_sql_query("SELECT * FROM trade_events ORDER BY seq", self.conn)),
        ):
            p = out_dir / f"{name}_{stamp}.csv"
            df.to_csv(p, index=False, encoding="utf-8")
            paths[name] = p
        return paths
