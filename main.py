"""
QuantSignal AI - consola profesional.

    python main.py                      menu interactivo
    python main.py analyze BTC-USD      analisis completo + reporte
    python main.py scan [--backtest]    escaner de la watchlist (50 activos)
    python main.py study                estudio multi-activo (6 estrategias x 50 activos)
    python main.py data                 descargar/actualizar datos del universo
    python main.py backtest ETH-USD     backtesting profesional
    python main.py journal              bitacora de operaciones
    python main.py report               reporte de la bitacora
    python main.py update               evaluar senales + paper trading
    python main.py app                  interfaz grafica (Streamlit)
"""

import argparse
import subprocess
import sys

from config import settings
from journal.repository import TradeJournal
from ui import console as C
from ui import views as V


# =========================================================
# ACCIONES
# =========================================================

def pick_symbol(prompt="Activo"):
    """Seleccion en dos pasos: clase de activo -> activo (o ticker libre)."""
    wl = set(settings.WATCHLIST)
    groups = [(n, [s for s in g if s in wl]) for n, g in settings.UNIVERSE.items()]
    groups = [(n, g) for n, g in groups if g]
    extra = [s for s in settings.WATCHLIST if all(s not in g for _, g in groups)]
    if extra:
        groups.append(("Mi watchlist", extra))
    opts = [(str(i), f"{name} ({len(g)})") for i, (name, g) in enumerate(groups, 1)]
    opts.append((str(len(groups) + 1), "Escribir otro ticker (Yahoo Finance)"))
    opts.append(("0", "Volver"))
    op = C.menu(prompt, opts)
    if op == "0":
        return None
    if int(op) == len(groups) + 1:
        t = C.ask("Ticker")
        return t.upper().strip() if t else None
    name, syms = groups[int(op) - 1]
    opts = [(str(i), f"{s:<10} {C.GRAY}{settings.NAMES.get(s, '')}{C.RESET}") for i, s in enumerate(syms, 1)]
    opts.append(("0", "Volver"))
    op = C.menu(name, opts)
    return None if op == "0" else syms[int(op) - 1]


def run(symbol, research=True):
    from core.analyzer import run_analysis
    print(f"\n  {C.GRAY}Descargando datos y calculando (indicadores, escenarios, backtests)...{C.RESET}")
    try:
        return run_analysis(symbol, research=research)
    except Exception as e:  # noqa: BLE001
        C.bullet(f"No se pudo analizar {symbol}: {e}", "bad")
        return None


def maybe_paper(a, journal):
    from paper_trading.trade_manager import open_virtual_trade
    rec = a["recommendation"]
    if (
        rec.get("verdict") == "FAVORABLE"
        and (rec.get("score") or 0) >= settings.PAPER_MIN_SCORE
        and rec["direction"] in ("LONG", "SHORT")
        and a["trade_plan"]["direction"] == rec["direction"]
    ):
        open_virtual_trade(a["symbol"], rec["direction"], a["trade_plan"], signal_id=a["_signal_id"],
                           journal=journal, interval=a["interval"])


def action_analyze(journal, symbol=None, open_report=True, interactive=True):
    from reports.asset_report import generate_asset_report
    from reports.export_report import export_report

    symbol = symbol or pick_symbol("Analizar activo")
    if not symbol:
        return
    a = run(symbol)
    if a is None:
        return
    a["_signal_id"] = journal.log_signal(a)

    V.print_recommendation(a)
    V.print_plan(a)
    V.print_scenarios(a["scenarios"])
    V.print_research(a["research"], show_table=False)

    maybe_paper(a, journal)
    export_report(symbol, a["signal"], a["confluence_score"], a["trade_plan"], a["backtest_v2"])
    path = generate_asset_report(a)
    C.bullet(f"Senal registrada en la bitacora: {a['_signal_id'][:8]}", "ok")
    C.bullet(f"Reporte: {path}", "ok")
    if open_report:
        C.open_file(path)

    while interactive:
        op = C.menu("Siguiente paso", [
            ("1", "Ver detalle tecnico completo (estructura, OB, FVG, Fibonacci...)"),
            ("2", "Ver comparacion de estrategias (backtesting)"),
            ("3", "Registrar una operacion manual con este plan"),
            ("4", "Abrir el reporte"),
            ("0", "Volver al menu"),
        ])
        if op == "0":
            break
        if op == "1":
            legacy_detail(a)
        elif op == "2":
            V.print_research(a["research"])
        elif op == "3":
            from journal.cli import register_trade
            register_trade(journal)
        elif op == "4":
            C.open_file(path)


def legacy_detail(a):
    from strategy.show_confluence import show_confluence
    from structure.debug_structure import show_structure
    from structure.show_fibonacci import show_fibonacci
    from structure.show_fvg import show_fvg
    from structure.show_hh_hl import show_hh_hl
    from structure.show_liquidity import show_liquidity
    from structure.show_order_blocks import show_order_blocks
    from structure.show_pd_zone import show_pd_zone
    show_structure(a["df"])
    show_hh_hl(*a["hh_hl"])
    show_order_blocks(a["order_blocks"])
    show_liquidity(a["liquidity"])
    show_fvg(a["fvg"])
    show_pd_zone(a["pd_zone"])
    show_fibonacci(a["fib_levels"])
    show_confluence(a["confluence_score"], a["factors"])
    C.section("Indicadores")
    C.kv([(k, C.fmt_num(v, 2)) for k, v in a["indicators"].items()], cols=3, key_w=12)


def action_scan(journal, open_report=True, with_backtest=None):
    from analytics.scanner import scan
    from reports.scanner_report import generate_scanner_report
    n = len(settings.WATCHLIST)
    C.section(f"Escaner de {n} activos")
    if with_backtest is None:
        with_backtest = C.confirm(f"Incluir backtesting de 6 estrategias por activo? (~{max(1, n * 5 // 60)} min; "
                                  f"sin el, ~{max(1, n * 2 // 60)} min)", default=False)
    res = scan(progress=C.progress, log=lambda *x: None, with_backtest=with_backtest)
    for sym, a in res["analyses"].items():
        journal.log_signal(a)
    V.print_scan(res)
    path = generate_scanner_report(res)
    C.bullet(f"{len(res['analyses'])} senales registradas en la bitacora", "ok")
    C.bullet(f"Reporte: {path}", "ok")
    if open_report:
        C.open_file(path)
    return res


def action_backtest(journal, symbol=None, open_report=True):
    from reports.asset_report import generate_asset_report
    symbol = symbol or pick_symbol("Backtesting profesional")
    if not symbol:
        return
    a = run(symbol)
    if a is None:
        return
    V.print_research(a["research"])
    r = a["research"]
    if r.get("segments") is not None and len(r["segments"]):
        C.section("Estabilidad por segmentos de tiempo")
        C.table(r["segments"])
    if r.get("ruin_table") is not None and len(r["ruin_table"]):
        C.section("Riesgo de ruina segun % arriesgado por operacion")
        C.table(r["ruin_table"])
    C.section("Sensibilidad (expectativa R: filas = stop ATR, columnas = objetivo R)")
    print(r["grid_pivot"].round(3).to_string())
    path = generate_asset_report(a)
    C.bullet(f"Reporte: {path}", "ok")
    if open_report:
        C.open_file(str(path))


def action_study(open_report=True):
    from analytics.universe_study import universe_study
    from reports.study_report import generate_study_report
    C.section(f"Estudio multi-activo: 6 estrategias x {len(settings.WATCHLIST)} activos")
    st = universe_study(progress=C.progress, log=lambda *x: None)
    s = st["summary"]
    C.table(s, columns=["estrategia", "trades", "activos_con_ops", "win_rate", "expectancy_r", "exp_ci_low",
                        "exp_ci_high", "p_value", "dsr", "consistencia_%", "veredicto"],
            headers=["Estrategia", "Ops", "Activos", "Win%", "E[R]", "IC95 bajo", "IC95 alto", "p", "DSR",
                     "Consist.%", "Veredicto"],
            formats={"veredicto": C.verdict_badge, "dsr": lambda v: "-" if v is None else f"{v * 100:.0f}%",
                     "expectancy_r": lambda v: C.colored(v, C.fmt_num(v, 3, sign=True)),
                     "p_value": lambda v: C.fmt_num(v, 4)})
    C.bullet(f"{len(st['trades']):,} operaciones simuladas en {len(st['symbols'])} activos", "ok")
    if st.get("trades_path"):
        C.bullet(f"Casos de estudio guardados: {st['trades_path']}", "ok")
    for k, v in st["errors"].items():
        C.bullet(f"{k}: {v}", "warn")
    path = generate_study_report(st)
    C.bullet(f"Reporte: {path}", "ok")
    if open_report:
        C.open_file(path)


def action_data():
    from data.cache import cache_status, prefetch
    stt = cache_status()
    C.section("Datos locales")
    C.bullet(f"{int(stt['en_cache'].sum())}/{len(stt)} activos en cache · {int(stt['fresco'].sum())} actualizados "
             f"(< {settings.CACHE_MAX_AGE_HOURS:g} h)")
    if C.confirm("Descargar/actualizar ahora todo el universo?", default=True):
        info = prefetch(settings.WATCHLIST, force=C.confirm("Forzar descarga aunque este fresco?", default=False),
                        progress=C.progress, log=lambda m: C.bullet(m, "warn"))
        C.bullet(f"Descargados {len(info['ok'])} · ya frescos {len(info['cached'])} · fallidos {len(info['failed'])}", "ok")
        for k, v in info["failed"].items():
            C.bullet(f"{k}: {v}", "bad")


def action_update(journal):
    from journal.enrichment import enrich_pending, evaluate_signals
    from paper_trading.trade_monitor import update_paper_trades
    C.section("Actualizando resultados")
    ev = evaluate_signals(journal)
    C.bullet(f"Senales evaluadas: {ev['evaluated']} · aun abiertas: {ev['open']} · errores: {ev['errors']}", "ok")
    n = update_paper_trades(journal, log=lambda m: C.bullet(m.strip()))
    C.bullet(f"Operaciones de paper trading cerradas: {n}", "ok")
    res = enrich_pending(journal)
    if res:
        C.bullet(f"Operaciones enriquecidas: {sum(1 for v in res.values() if v == 'OK')}/{len(res)}", "ok")


def action_ai(journal):
    import json
    from journal.cli import train
    op = C.menu("Inteligencia artificial", [
        ("1", "Construir dataset y entrenar (mercado + senales + tus operaciones)"),
        ("2", "Ver ficha del modelo actual"),
        ("0", "Volver"),
    ])
    if op == "1":
        train(journal)
    elif op == "2":
        p = settings.MODELS_DIR / "model_card.json"
        if not p.exists():
            C.bullet("Aun no hay modelo entrenado", "warn")
            return
        card = json.loads(p.read_text(encoding="utf-8"))
        C.section(f"Modelo entrenado {card['trained_at']}")
        C.table([{"conjunto": k, **v} for k, v in card["metrics"].items()])
        if card.get("reliability"):
            C.section("Calibracion (probabilidad predicha vs frecuencia real)")
            C.table(card["reliability"])
        if card.get("drift_psi"):
            C.section("Deriva de datos (PSI)")
            C.table(card["drift_psi"][:8])
        for w in card.get("warnings", []):
            C.bullet(w, "warn")


def action_reports(journal):
    import os
    from reports.html_report import generate_html_report
    op = C.menu("Reportes", [
        ("1", "Reporte de la bitacora (tus operaciones + estadistica avanzada)"),
        ("2", "Abrir la carpeta de reportes"),
        ("3", "Abrir el ultimo reporte generado"),
        ("4", "Exportar bitacora a CSV"),
        ("0", "Volver"),
    ])
    settings.ensure_dirs()
    if op == "1":
        p = generate_html_report(journal)
        C.bullet(f"Reporte: {p}", "ok")
        C.open_file(p)
    elif op == "2":
        if os.name == "nt":
            os.startfile(settings.REPORTS_DIR)  # noqa: S606
        else:
            C.open_file(settings.REPORTS_DIR)
    elif op == "3":
        files = sorted(settings.REPORTS_DIR.glob("*.html"), key=lambda p: p.stat().st_mtime)
        if files:
            C.open_file(files[-1])
            C.bullet(str(files[-1]), "ok")
        else:
            C.bullet("No hay reportes todavia", "warn")
    elif op == "4":
        for k, p in journal.export_csv().items():
            C.bullet(f"{k}: {p}", "ok")


def action_settings():
    while True:
        C.section("Configuracion actual")
        items = [
            ("ACCOUNT_SIZE", "Capital de la cuenta ($)"), ("RISK_PERCENT", "Riesgo por operacion (%)"),
            ("MAX_RISK_PERCENT", "Riesgo maximo aunque Kelly sugiera mas (%)"),
            ("WATCHLIST", "Watchlist (separada por comas)"), ("INTERVAL", "Temporalidad (1d, 1h, 4h, 1wk)"),
            ("PERIOD", "Historico a descargar (2y, 5y, max)"), ("FEE_PCT", "Comision por lado (0.001 = 0.1%)"),
            ("SLIPPAGE_PCT", "Slippage por lado"), ("PAPER_MIN_SCORE", "Score minimo para paper trading"),
            ("LOCAL_TZ", "Zona horaria"),
        ]
        opts = []
        for i, (k, label) in enumerate(items, 1):
            v = getattr(settings, k)
            v = ", ".join(v) if isinstance(v, list) else v
            opts.append((str(i), f"{label}: {C.BOLD}{v}{C.RESET}"))
        opts.append(("0", "Volver"))
        op = C.menu("Configuracion (se guarda en config/user_settings.json)", opts)
        if op == "0":
            return
        key = items[int(op) - 1][0]
        cur = getattr(settings, key)
        raw = C.ask(f"Nuevo valor para {key}", ", ".join(cur) if isinstance(cur, list) else cur)
        if raw is None:
            continue
        try:
            if isinstance(cur, list):
                val = [s.strip().upper() for s in str(raw).split(",") if s.strip()]
            elif isinstance(cur, float) or isinstance(cur, int):
                val = float(raw)
            else:
                val = str(raw)
            settings.save_user_settings(**{key: val})
            C.bullet(f"{key} = {val}", "ok")
        except (ValueError, KeyError) as e:
            C.bullet(f"Valor invalido: {e}", "bad")


def launch_app():
    C.bullet("Abriendo la interfaz grafica en el navegador (Ctrl+C para cerrar)...", "info")
    subprocess.call([sys.executable, "-m", "streamlit", "run", str(settings.BASE_DIR / "app.py")])


# =========================================================
# MENU
# =========================================================

def main_menu():
    settings.ensure_dirs()
    with TradeJournal() as journal:
        migrated = journal.migrate_legacy_csv()
        if migrated:
            C.bullet(f"Se migraron {migrated} registros del trade_journal.csv a la bitacora", "ok")
        while True:
            C.banner("QUANTSIGNAL AI", V.status_line(journal))
            op = C.menu("Menu principal", [
                ("", "Analisis"),
                ("1", "Analizar un activo (recomendacion, escenarios, backtest, reporte)"),
                ("2", f"Escaner de oportunidades ({len(settings.WATCHLIST)} activos + comparacion)"),
                ("", "Investigacion"),
                ("3", "Backtesting profesional de un activo (estrategias, Monte Carlo, walk-forward)"),
                ("10", f"Estudio multi-activo (6 estrategias x {len(settings.WATCHLIST)} activos)"),
                ("", "Operacion"),
                ("4", "Bitacora de operaciones (registrar, gestionar, auditar)"),
                ("5", "Actualizar resultados (senales, paper trading, enriquecimiento)"),
                ("", "IA y reportes"),
                ("6", "Inteligencia artificial (entrenar, evaluar modelo)"),
                ("7", "Reportes"),
                ("", "Sistema"),
                ("8", "Configuracion"),
                ("11", "Datos: descargar / actualizar el universo"),
                ("9", "Abrir interfaz grafica (Streamlit)"),
                ("0", "Salir"),
            ])
            try:
                if op == "0":
                    print(f"\n  {C.GRAY}Hasta pronto.{C.RESET}\n")
                    break
                {"1": lambda: action_analyze(journal),
                 "2": lambda: action_scan(journal),
                 "3": lambda: action_backtest(journal),
                 "4": lambda: __import__("journal.cli", fromlist=["menu"]).menu(journal),
                 "5": lambda: action_update(journal),
                 "6": lambda: action_ai(journal),
                 "7": lambda: action_reports(journal),
                 "8": action_settings,
                 "10": action_study,
                 "11": action_data,
                 "9": launch_app}[op]()
            except KeyboardInterrupt:
                print(f"\n  {C.YELLOW}(cancelado){C.RESET}")


def cli(argv=None):
    p = argparse.ArgumentParser(prog="quantsignal", description="QuantSignal AI")
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("analyze", help="analisis completo de un activo")
    a.add_argument("symbol")
    a.add_argument("--no-open", action="store_true", help="no abrir el reporte")
    s = sub.add_parser("scan", help="escaner de la watchlist")
    s.add_argument("--no-open", action="store_true")
    s.add_argument("--backtest", action="store_true", help="incluir backtesting por activo (mas lento)")
    sd = sub.add_parser("study", help="estudio multi-activo (6 estrategias x universo)")
    sd.add_argument("--no-open", action="store_true")
    sub.add_parser("data", help="descargar/actualizar datos del universo")
    b = sub.add_parser("backtest", help="backtesting profesional")
    b.add_argument("symbol")
    b.add_argument("--no-open", action="store_true")
    sub.add_parser("journal", help="bitacora de operaciones")
    sub.add_parser("report", help="reporte de la bitacora")
    sub.add_parser("update", help="evaluar senales y paper trading")
    sub.add_parser("app", help="interfaz grafica")
    args = p.parse_args(argv)

    if args.cmd is None:
        return main_menu()
    if args.cmd == "app":
        return launch_app()
    settings.ensure_dirs()
    with TradeJournal() as j:
        j.migrate_legacy_csv()
        if args.cmd == "analyze":
            action_analyze(j, args.symbol.upper(), open_report=not args.no_open, interactive=False)
        elif args.cmd == "scan":
            action_scan(j, open_report=not args.no_open, with_backtest=args.backtest)
        elif args.cmd == "study":
            action_study(open_report=not args.no_open)
        elif args.cmd == "data":
            from data.cache import prefetch
            info = prefetch(settings.WATCHLIST, progress=C.progress)
            C.bullet(f"Descargados {len(info['ok'])} · frescos {len(info['cached'])} · fallidos {len(info['failed'])}", "ok")
        elif args.cmd == "backtest":
            action_backtest(j, args.symbol.upper(), open_report=not args.no_open)
        elif args.cmd == "journal":
            from journal.cli import menu
            menu(j)
        elif args.cmd == "report":
            from reports.html_report import generate_html_report
            path = generate_html_report(j)
            C.bullet(f"Reporte: {path}", "ok")
            C.open_file(path)
        elif args.cmd == "update":
            action_update(j)


if __name__ == "__main__":
    cli()
