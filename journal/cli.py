"""
Menu de consola de la bitacora. Se abre desde main.py (opcion 7)
o directamente con:  python -m journal.cli
"""

import json

import pandas as pd

from config import settings
from journal.repository import (
    EMOTIONS, EXIT_REASONS, MISTAKES, SETUPS, JournalError, TradeJournal, utc_to_local,
)


# =========================================================
# HELPERS DE ENTRADA
# =========================================================

def ask(prompt, default=None, cast=str, required=False):
    suffix = f" [{default}]" if default not in (None, "") else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if raw == "":
            if default not in (None, ""):
                return cast(default) if cast is not str else default
            if not required:
                return None
            print("  Campo obligatorio")
            continue
        try:
            return cast(raw.replace(",", ".")) if cast in (float, int) else cast(raw)
        except ValueError:
            print("  Valor invalido")


def choose(prompt, options, allow_free=True, multi=False):
    print(f"\n{prompt}")
    for i, o in enumerate(options, 1):
        print(f"  {i:>2}. {o}")
    hint = "numeros separados por coma" if multi else "numero"
    raw = input(f"  Elige ({hint}{' o escribe otro' if allow_free else ''}, Enter = ninguno): ").strip()
    if not raw:
        return [] if multi else None
    picks = []
    for part in raw.split(",") if multi else [raw]:
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= len(options):
            picks.append(options[int(part) - 1])
        elif allow_free and part:
            picks.append(part)
    return picks if multi else (picks[0] if picks else None)


def yes_no(prompt, default=None):
    d = {True: "s", False: "n", None: ""}[default]
    raw = input(f"{prompt} (s/n) [{d}]: ").strip().lower() or d
    if raw.startswith("s"):
        return True
    if raw.startswith("n"):
        return False
    return None


def fmt_local(ts):
    t = utc_to_local(ts)
    return t.strftime("%Y-%m-%d %H:%M") if t is not None else "-"


def print_trades(df):
    if len(df) == 0:
        print("\n  (sin operaciones)")
        return
    print()
    print(f"  {'ID':<9}{'FUENTE':<8}{'ACTIVO':<10}{'DIR':<6}{'ESTADO':<10}{'ENTRADA':>12}"
          f"{'STOP':>12}{'TP':>12}{'R':>7}  FECHA ENTRADA")
    for _, t in df.iterrows():
        r = "" if pd.isna(t["r_multiple"]) else f"{t['r_multiple']:.2f}"
        tp = "" if pd.isna(t["take_profit"]) else f"{t['take_profit']:.2f}"
        print(f"  {t['id'][:8]:<9}{t['source']:<8}{t['symbol']:<10}{t['direction']:<6}{t['status']:<10}"
              f"{t['entry_price']:>12.2f}{t['stop_current']:>12.2f}{tp:>12}{r:>7}  {fmt_local(t['entry_time'])}")


def pick_trade(j, statuses=("OPEN",)):
    df = j.list_trades(status=list(statuses))
    print_trades(df)
    if len(df) == 0:
        return None
    tid = ask("\nID de la operacion (primeros 8 caracteres)")
    return tid


# =========================================================
# ACCIONES
# =========================================================

def register_trade(j):
    print("\n=========== REGISTRAR OPERACION ===========")
    print("Fechas en hora local (" + settings.LOCAL_TZ + "), formato 2026-09-28 14:30. Enter = ahora.\n")

    symbol = ask("Activo (ej. BTC-USD, SPY, EURUSD=X)", required=True).upper()
    direction = choose("Direccion", ["LONG", "SHORT"], allow_free=False)
    if direction is None:
        print("Cancelado")
        return
    status = "PLANNED" if yes_no("Es solo un PLAN (orden aun no ejecutada)?", False) else "OPEN"
    entry_time = ask("Fecha/hora de entrada")
    entry = ask("Precio de entrada", cast=float, required=True)
    stop = ask("Stop loss", cast=float, required=True)
    tp = ask("Take profit", cast=float)
    risk_default = round(settings.ACCOUNT_SIZE * settings.RISK_PERCENT / 100, 2)
    qty = ask("Cantidad (unidades). Enter = calcular por riesgo", cast=float)
    risk = None
    if not qty:
        risk = ask("Monto a arriesgar ($)", default=risk_default, cast=float)
    interval = choose("Temporalidad principal de la operacion",
                      ["1m", "5m", "15m", "1h", "4h", "1d", "1wk"], allow_free=False) or "1d"

    # Vincular con una senal del sistema
    signal_id = None
    sig = j.list_signals(symbol=symbol, limit=5)
    if len(sig):
        print("\nSenales recientes del sistema para este activo:")
        for i, s in enumerate(sig.itertuples(), 1):
            print(f"  {i}. {fmt_local(s.created_at)} {s.signal} ({s.probability}) entrada {s.entry}")
        k = ask("Vincular a cual? (numero, Enter = ninguna)")
        if k and k.isdigit() and 1 <= int(k) <= len(sig):
            signal_id = sig.iloc[int(k) - 1]["id"]

    setup = choose("Setup / patron", SETUPS)
    timeframes = ask("Temporalidades revisadas (ej. 1d,4h,1h)")
    rationale = ask("Por que entras? (tesis)")
    confidence = ask("Confianza 1-5", cast=int)
    emotion = choose("Emocion al entrar", EMOTIONS)
    tags = ask("Etiquetas (separadas por coma)")
    screenshot = ask("Ruta de captura de pantalla (opcional)")

    try:
        tid = j.open_trade(
            symbol=symbol, direction=direction, entry_price=entry, stop=stop, take_profit=tp,
            quantity=qty, risk_amount=risk, entry_time=entry_time, status=status,
            interval=interval, signal_id=signal_id, setup=setup, timeframes=timeframes,
            rationale=rationale, confidence=confidence, emotion_entry=emotion, tags=tags,
            screenshot=screenshot,
        )
    except JournalError as e:
        print(f"\n❌ {e}")
        return

    t = j.get_trade(tid)
    print(f"\n✅ Operacion registrada -> ID {tid[:8]}  | riesgo ${t['risk_amount']:.2f} "
          f"| cantidad {t['quantity']:.6f}")

    if yes_no("Calcular ahora las features de mercado en tu entrada (requiere internet)?", True):
        from journal.enrichment import enrich_trade
        print("  ->", enrich_trade(j, tid))


def move_stop(j):
    tid = pick_trade(j, ("OPEN", "PLANNED"))
    if not tid:
        return
    new = ask("Nuevo stop", cast=float, required=True)
    reason = ask("Motivo (ej. breakeven, trailing)")
    try:
        j.update_stop(tid, new, reason)
        print("✅ Stop actualizado")
    except JournalError as e:
        print(f"❌ {e}")


def partial(j):
    tid = pick_trade(j)
    if not tid:
        return
    try:
        t = j.get_trade(tid)
        print(f"Posicion abierta: {t['remaining_qty']:.6f}")
        qty = ask("Cantidad a cerrar", cast=float, required=True)
        price = ask("Precio", cast=float, required=True)
        when = ask("Fecha/hora (Enter = ahora)")
        fees = ask("Comision", default=0, cast=float)
        j.partial_close(tid, qty, price, when, fees=fees)
        print("✅ Cierre parcial registrado")
    except JournalError as e:
        print(f"❌ {e}")


def close(j):
    tid = pick_trade(j)
    if not tid:
        return
    try:
        price = ask("Precio de salida", cast=float, required=True)
        when = ask("Fecha/hora de salida (Enter = ahora)")
        reason = choose("Motivo de salida", EXIT_REASONS) or "MANUAL"
        fees = ask("Comisiones totales", default=0, cast=float)
        print("\n--- Revision post-operacion (es lo que mas le ensena a la IA sobre ti) ---")
        followed = yes_no("Seguiste tu plan?")
        emotion_exit = choose("Emocion al salir", EMOTIONS)
        mistakes = choose("Errores cometidos", MISTAKES, multi=True)
        lessons = ask("Leccion aprendida")
        tid = j.close_trade(tid, price, when, reason, fees=fees, followed_plan=followed,
                            emotion_exit=emotion_exit, mistakes=mistakes, lessons=lessons)
        t = j.get_trade(tid)
        print(f"\n✅ Cerrada: PnL ${t['pnl']:.2f} | {t['r_multiple']:.2f} R")
        from journal.enrichment import enrich_trade
        if yes_no("Calcular MAE/MFE con datos de mercado?", True):
            print("  ->", enrich_trade(j, tid))
    except JournalError as e:
        print(f"❌ {e}")


def note(j):
    tid = pick_trade(j, ("OPEN", "PLANNED", "CLOSED"))
    if tid:
        try:
            j.add_note(tid, ask("Nota", required=True))
            print("✅ Nota agregada")
        except JournalError as e:
            print(f"❌ {e}")


def cancel(j):
    tid = pick_trade(j, ("OPEN", "PLANNED"))
    if tid:
        try:
            j.cancel_trade(tid, ask("Motivo"))
            print("✅ Operacion cancelada")
        except JournalError as e:
            print(f"❌ {e}")


def history(j):
    print_trades(j.list_trades())
    tid = ask("\nID para ver su auditoria (Enter = volver)")
    if not tid:
        return
    try:
        t = j.get_trade(tid)
    except JournalError as e:
        print(f"❌ {e}")
        return
    print(f"\n=== {t['symbol']} {t['direction']} ({t['source']}) - {t['status']} ===")
    for k in ("setup", "rationale", "confidence", "emotion_entry", "emotion_exit",
              "followed_plan", "mistakes", "lessons", "r_multiple", "pnl", "mae_r", "mfe_r",
              "features_status"):
        if t.get(k) not in (None, "", []):
            print(f"  {k:<15}: {t[k]}")
    print("\n  Linea de tiempo:")
    for _, e in j.get_events(t["id"]).iterrows():
        p = e["payload"]
        if "changes" in p:
            det = "; ".join(f"{k}: {v['before']} -> {v['after']}" for k, v in p["changes"].items())
            if p.get("reason"):
                det = f"[{p['reason']}] {det}"
        elif "text" in p:
            det = p["text"]
        else:
            det = json.dumps({k: p[k] for k in list(p)[:6]}, ensure_ascii=False, default=str)
        print(f"  {fmt_local(e['ts'])} {e['event_type']:<14} {e['actor']:<7} {det[:120]}")
        print(f"  {'':16} hash {e['hash'][:16]}")


def import_csv(j):
    print("\nColumnas minimas: symbol, direction (LONG/SHORT/BUY/SELL), entry_price, stop, quantity")
    print("Opcionales: entry_time, exit_time, exit_price, take_profit, fees, setup, notes, broker_ref")
    path = ask("Ruta del CSV", required=True).strip('"')
    try:
        res = j.import_trades_csv(path)
    except FileNotFoundError:
        print("❌ No existe el archivo")
        return
    print(f"✅ Importadas {res['imported']} | duplicadas {res['skipped']} | errores {len(res['errors'])}")
    for e in res["errors"][:10]:
        print("   ", e)


def train(j):
    from ml.dataset import build_dataset, save_dataset
    from ml.model import train_model
    include = yes_no(f"Incluir muestras historicas de los {len(settings.WATCHLIST)} activos del universo (~1-2 min)?", True)
    print("\nConstruyendo dataset...")
    ds = build_dataset(j, include_market=bool(include))
    if len(ds) == 0:
        print("❌ Dataset vacio")
        return
    path, meta = save_dataset(ds)
    print(f"✅ Dataset: {path}\n   {meta['by_source']}")
    try:
        card = train_model(ds)
    except ValueError as e:
        print(f"❌ {e}")
        return
    print("\n✅ Modelo entrenado")
    for k, v in card["metrics"].items():
        print(f"   {k:<24} {v}")
    print("\n   Variables mas importantes:")
    for f in card["importance"][:8]:
        print(f"     {f['feature']:<22} {f['importance']}")
    for w in card["warnings"]:
        print("   ⚠", w)


def menu(j=None):
    own = j is None
    j = j or TradeJournal()
    migrated = j.migrate_legacy_csv()
    if migrated:
        print(f"\n(Se migraron {migrated} registros del trade_journal.csv antiguo)")

    actions = {
        "1": ("Registrar operacion", register_trade),
        "2": ("Ver operaciones abiertas", lambda j: print_trades(j.list_trades(status=["OPEN", "PLANNED"]))),
        "3": ("Mover stop", move_stop),
        "4": ("Cierre parcial", partial),
        "5": ("Cerrar operacion (con revision)", close),
        "6": ("Agregar nota", note),
        "7": ("Cancelar operacion", cancel),
        "8": ("Historial y auditoria de una operacion", history),
        "9": ("Enriquecer operaciones pendientes (features + MAE/MFE)", None),
        "10": ("Evaluar resultado de senales pasadas", None),
        "11": ("Actualizar paper trading (cerrar por SL/TP)", None),
        "12": ("Importar operaciones desde CSV", import_csv),
        "13": ("Generar reporte HTML", None),
        "14": ("Construir dataset y entrenar IA", train),
        "15": ("Verificar integridad de la bitacora", None),
        "16": ("Exportar todo a CSV", None),
    }

    try:
        while True:
            print("\n=========== BITACORA / IA ===========")
            for k, (label, _) in actions.items():
                print(f"{k:>3}. {label}")
            print("  0. Volver")
            op = input("\nOpcion: ").strip()
            if op == "0":
                break
            if op not in actions:
                print("Opcion invalida")
                continue
            try:
                if op == "9":
                    from journal.enrichment import enrich_pending
                    print(enrich_pending(j) or "Nada pendiente")
                elif op == "10":
                    from journal.enrichment import evaluate_signals
                    print(evaluate_signals(j))
                elif op == "11":
                    from paper_trading.trade_monitor import update_paper_trades
                    print(f"Cerradas: {update_paper_trades(j)}")
                elif op == "13":
                    from reports.html_report import generate_html_report
                    print("✅", generate_html_report(j))
                elif op == "15":
                    print(j.verify_integrity())
                elif op == "16":
                    for k, p in j.export_csv().items():
                        print(f"✅ {k}: {p}")
                else:
                    actions[op][1](j)
            except KeyboardInterrupt:
                print("\n(cancelado)")
    finally:
        if own:
            j.close()


if __name__ == "__main__":
    menu()
