"""
QuantSignal AI - interfaz grafica.

    streamlit run app.py

Registrar y gestionar operaciones, ver su auditoria, el panel de rendimiento,
analizar activos y entrenar la IA con tu historial.
"""

import json
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from config import settings
from journal.repository import (
    EMOTIONS, EXIT_REASONS, MISTAKES, SETUPS, JournalError, TradeJournal, utc_to_local,
)
from reports import performance as perf

settings.ensure_dirs()

st.set_page_config(page_title="QuantSignal AI", page_icon="📈", layout="wide")

# Una conexion por ejecucion del script (SQLite no se comparte entre hilos)
J = TradeJournal()
if J.migrate_legacy_csv():
    st.toast("Se migro el trade_journal.csv antiguo a la bitacora")

INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d", "1wk"]


# =========================================================
# HELPERS
# =========================================================

def local_str(ts):
    t = utc_to_local(ts)
    return t.strftime("%Y-%m-%d %H:%M") if t is not None else ""


def trade_label(t):
    r = "" if pd.isna(t["r_multiple"]) else f" | {t['r_multiple']:+.2f}R"
    return (f"{t['id'][:8]} | {t['symbol']} {t['direction']} | {t['status']} | "
            f"{local_str(t['entry_time'])} @ {t['entry_price']:,.4g}{r}")


def combine_local(d, t):
    return datetime.combine(d, t).strftime("%Y-%m-%d %H:%M")


def now_local():
    return pd.Timestamp.now(tz=settings.LOCAL_TZ)


def show_error(e):
    st.error(f"❌ {e}")


def fmt_df(df, cols=None):
    if df is None or len(df) == 0:
        return df
    df = df.copy()
    for c in ("entry_time", "exit_time", "created_at", "ts"):
        if c in df.columns:
            df[c] = df[c].apply(local_str)
    if "id" in df.columns:
        df["id"] = df["id"].str[:8]
    return df[cols] if cols else df


# =========================================================
# PAGINAS
# =========================================================

def page_panel():
    st.header("📊 Panel de rendimiento")
    trades = J.list_trades()
    signals = J.list_signals()

    fuentes = st.multiselect("Fuentes", ["MANUAL", "LIVE", "IMPORT", "PAPER"],
                             default=["MANUAL", "LIVE", "IMPORT", "PAPER"])
    if len(trades):
        trades = trades[trades["source"].isin(fuentes)]

    s = perf.summary(trades, settings.ACCOUNT_SIZE)
    if not s.get("trades"):
        st.info("Aun no hay operaciones cerradas. Empieza en **➕ Registrar operacion**.")
    else:
        c = st.columns(5)
        c[0].metric("Operaciones", s["trades"])
        c[1].metric("Win rate", f"{s['win_rate']:.1f}%")
        c[2].metric("Profit factor", s["profit_factor"] if s["profit_factor"] is not None else "-")
        c[3].metric("Expectativa", f"{s['expectancy_r']:+.2f} R")
        c[4].metric("R total", f"{s['total_r']:+.2f} R")
        c = st.columns(5)
        c[0].metric("PnL", f"${s['total_pnl']:,.2f}")
        c[1].metric("Max drawdown", f"{s['max_drawdown_pct']:.1f}%")
        c[2].metric("Sharpe / trade", s["sharpe_per_trade"] if s["sharpe_per_trade"] is not None else "-")
        c[3].metric("Racha perdedora", s["max_loss_streak"])
        c[4].metric("Plan respetado", f"{s['plan_adherence_pct']:.0f}%" if s["plan_adherence_pct"] is not None else "-")

        eq = perf.equity_series(trades, settings.ACCOUNT_SIZE).set_index("exit_time")
        a, b = st.columns(2)
        a.subheader("Equity ($)")
        a.line_chart(eq["equity"])
        b.subheader("R acumulado")
        b.line_chart(eq["cum_r"])
        st.subheader("Drawdown (%)")
        st.area_chart(-eq["drawdown_pct"])

        a, b = st.columns(2)
        for col, by, title in [(a, "setup", "Por setup"), (b, "emotion_entry", "Por emocion al entrar")]:
            col.subheader(title)
            bd = perf.breakdown(trades, by)
            if len(bd):
                col.bar_chart(bd.set_index(by)["total_r"])
                col.dataframe(bd, hide_index=True, width="stretch")

        a, b = st.columns(2)
        a.subheader("Seguiste el plan?")
        plan = perf.breakdown(trades.assign(plan=trades["followed_plan"].map({1: "Si", 0: "No"})), "plan")
        a.dataframe(plan, hide_index=True, width="stretch")
        b.subheader("Costo de los errores (R)")
        b.dataframe(perf.mistakes_breakdown(trades), hide_index=True, width="stretch")

        a, b = st.columns(2)
        a.subheader("Por activo")
        a.dataframe(perf.breakdown(trades, "symbol"), hide_index=True, width="stretch")
        b.subheader("Por fuente")
        b.dataframe(perf.breakdown(trades, "source"), hide_index=True, width="stretch")

    st.subheader("Senales del sistema (resultado evaluado)")
    a, b = st.columns(2)
    a.dataframe(perf.signals_summary(signals), hide_index=True, width="stretch")
    svy = perf.system_vs_you(J.list_trades(), signals)
    b.caption("Tu resultado real vs el resultado teorico de la senal que seguiste")
    b.dataframe(fmt_df(svy), hide_index=True, width="stretch")

    st.divider()
    if st.button("🧾 Generar reporte HTML"):
        from reports.html_report import generate_html_report
        path = generate_html_report(J)
        st.success(f"Reporte guardado en {path}")
        st.download_button("Descargar reporte", Path(path).read_bytes(), file_name=Path(path).name,
                           mime="text/html")


def page_register():
    st.header("➕ Registrar operacion")
    st.caption(f"Las fechas se escriben en tu hora local ({settings.LOCAL_TZ}).")

    pre = st.session_state.get("prefill", {})

    symbol = st.text_input("Activo (ticker de Yahoo: BTC-USD, SPY, EURUSD=X, GC=F...)",
                           value=pre.get("symbol", "")).upper().strip()

    signal_id = None
    if symbol:
        sig = J.list_signals(symbol=symbol, limit=10)
        if len(sig):
            opts = ["(ninguna)"] + [
                f"{s.id[:8]} | {local_str(s.created_at)} | {s.signal} ({s.probability}) | entrada {s.entry}"
                for s in sig.itertuples()
            ]
            default = 0
            if pre.get("signal_id"):
                for k, o in enumerate(opts):
                    if o.startswith(pre["signal_id"][:8]):
                        default = k
            pick = st.selectbox("Vincular a una senal del sistema", opts, index=default,
                                help="Permite medir si tu ejecucion mejora o empeora la senal")
            if pick != "(ninguna)":
                signal_id = sig.iloc[opts.index(pick) - 1]["id"]

    with st.form("nueva_operacion", clear_on_submit=False):
        c = st.columns(3)
        direction = c[0].radio("Direccion", ["LONG", "SHORT"], horizontal=True,
                               index=0 if pre.get("direction", "LONG") == "LONG" else 1)
        status = c[1].radio("Estado", ["OPEN", "PLANNED"], horizontal=True,
                            help="PLANNED = orden pendiente, aun no ejecutada")
        interval = c[2].selectbox("Temporalidad", INTERVALS, index=INTERVALS.index(pre.get("interval", "1d")))

        n = now_local()
        c = st.columns(2)
        d = c[0].date_input("Fecha de entrada", value=n.date())
        t = c[1].time_input("Hora de entrada", value=n.time().replace(second=0, microsecond=0))

        c = st.columns(3)
        entry = c[0].number_input("Precio de entrada", min_value=0.0, value=float(pre.get("entry", 0.0)), format="%.6f")
        stop = c[1].number_input("Stop loss", min_value=0.0, value=float(pre.get("stop", 0.0)), format="%.6f")
        tp = c[2].number_input("Take profit (0 = sin TP)", min_value=0.0, value=float(pre.get("tp", 0.0)), format="%.6f")

        c = st.columns(2)
        qty = c[0].number_input("Cantidad (0 = calcular por riesgo)", min_value=0.0, value=0.0, format="%.8f")
        risk = c[1].number_input("Riesgo en $ (si no pones cantidad)", min_value=0.0,
                                 value=float(settings.ACCOUNT_SIZE * settings.RISK_PERCENT / 100))

        st.markdown("**Contexto de la decision** (esto es lo que la IA aprende de ti)")
        c = st.columns(3)
        setup = c[0].selectbox("Setup", SETUPS, index=SETUPS.index(pre["setup"]) if pre.get("setup") in SETUPS else 0)
        emotion = c[1].selectbox("Emocion al entrar", EMOTIONS)
        confidence = c[2].slider("Confianza", 1, 5, 3)
        timeframes = st.multiselect("Temporalidades revisadas", INTERVALS, default=[interval])
        rationale = st.text_area("Tesis: por que entras?", value=pre.get("rationale", ""))
        tags = st.text_input("Etiquetas (separadas por coma)")
        shot = st.file_uploader("Captura del grafico", type=["png", "jpg", "jpeg", "webp"])
        enrich = st.checkbox("Calcular features de mercado en la entrada (requiere internet)", value=True)

        submitted = st.form_submit_button("Guardar operacion", type="primary")

    if submitted:
        if not symbol:
            show_error("Falta el activo")
            return
        shot_path = None
        if shot is not None:
            shot_path = settings.SCREENSHOTS_DIR / f"{uuid.uuid4().hex[:8]}_{shot.name}"
            shot_path.write_bytes(shot.getvalue())
        try:
            tid = J.open_trade(
                symbol=symbol, direction=direction, entry_price=entry, stop=stop,
                take_profit=tp or None, quantity=qty or None, risk_amount=risk or None,
                entry_time=combine_local(d, t), status=status, interval=interval,
                signal_id=signal_id, setup=setup, timeframes=",".join(timeframes),
                rationale=rationale, confidence=confidence, emotion_entry=emotion,
                tags=tags, screenshot=str(shot_path) if shot_path else None,
            )
        except JournalError as e:
            show_error(e)
            return
        st.session_state.pop("prefill", None)
        tr = J.get_trade(tid)
        st.success(f"✅ Operacion {tid[:8]} registrada | riesgo ${tr['risk_amount']:.2f} | cantidad {tr['quantity']:.6f}")
        if enrich:
            from journal.enrichment import enrich_trade
            with st.spinner("Descargando datos y calculando features..."):
                st.info(f"Features: {enrich_trade(J, tid)}")


def page_manage():
    st.header("🛠 Gestionar operaciones abiertas")
    df = J.list_trades(status=["OPEN", "PLANNED"])
    if len(df) == 0:
        st.info("No hay operaciones abiertas.")
        return
    labels = [trade_label(t) for _, t in df.iterrows()]
    pick = st.selectbox("Operacion", labels)
    t = J.get_trade(df.iloc[labels.index(pick)]["id"])

    c = st.columns(5)
    c[0].metric("Entrada", f"{t['entry_price']:,.6g}")
    c[1].metric("Stop actual", f"{t['stop_current']:,.6g}",
                delta=f"{t['stop_current'] - t['stop_initial']:+,.4g}" if t["stop_current"] != t["stop_initial"] else None)
    c[2].metric("Take profit", f"{t['take_profit']:,.6g}" if t["take_profit"] else "-")
    c[3].metric("Posicion abierta", f"{t['remaining_qty']:,.6g}")
    c[4].metric("PnL realizado", f"${t['realized_pnl'] or 0:,.2f}")

    tabs = st.tabs(["Cerrar", "Mover stop", "Cierre parcial", "Nota", "Editar", "Activar / Cancelar"])

    with tabs[0], st.form("cerrar"):
        c = st.columns(3)
        price = c[0].number_input("Precio de salida", min_value=0.0, format="%.6f")
        n = now_local()
        d = c[1].date_input("Fecha", value=n.date())
        tm = c[2].time_input("Hora", value=n.time().replace(second=0, microsecond=0))
        c = st.columns(3)
        reason = c[0].selectbox("Motivo", EXIT_REASONS)
        fees = c[1].number_input("Comisiones", min_value=0.0)
        followed = c[2].radio("Seguiste el plan?", ["Si", "No"], horizontal=True)
        emotion_exit = st.selectbox("Emocion al salir", EMOTIONS)
        mistakes = st.multiselect("Errores cometidos", MISTAKES)
        lessons = st.text_area("Leccion aprendida")
        if st.form_submit_button("Cerrar operacion", type="primary"):
            try:
                J.close_trade(t["id"], price, combine_local(d, tm), reason, fees=fees,
                              followed_plan=followed == "Si", emotion_exit=emotion_exit,
                              mistakes=mistakes, lessons=lessons)
                from journal.enrichment import enrich_trade
                with st.spinner("Calculando MAE/MFE..."):
                    enrich_trade(J, t["id"])
                c = J.get_trade(t["id"])
                st.success(f"Cerrada: ${c['pnl']:,.2f} | {c['r_multiple']:+.2f} R")
            except JournalError as e:
                show_error(e)

    with tabs[1], st.form("stop"):
        new = st.number_input("Nuevo stop", value=float(t["stop_current"]), format="%.6f")
        why = st.text_input("Motivo (breakeven, trailing...)")
        if st.form_submit_button("Actualizar stop"):
            try:
                J.update_stop(t["id"], new, why)
                st.success("Stop actualizado")
                st.rerun()
            except JournalError as e:
                show_error(e)

    with tabs[2], st.form("parcial"):
        c = st.columns(3)
        q = c[0].number_input("Cantidad", min_value=0.0, max_value=float(t["remaining_qty"]), format="%.8f")
        p = c[1].number_input("Precio", min_value=0.0, format="%.6f")
        f = c[2].number_input("Comision", min_value=0.0)
        if st.form_submit_button("Registrar parcial"):
            try:
                J.partial_close(t["id"], q, p, fees=f)
                st.success("Parcial registrado")
                st.rerun()
            except JournalError as e:
                show_error(e)

    with tabs[3], st.form("nota"):
        text = st.text_area("Nota (que ves en el mercado, dudas, cambios de plan...)")
        if st.form_submit_button("Agregar nota") and text:
            J.add_note(t["id"], text)
            st.success("Nota agregada")

    with tabs[4], st.form("editar"):
        setup = st.selectbox("Setup", SETUPS, index=SETUPS.index(t["setup"]) if t["setup"] in SETUPS else 0)
        tp = st.number_input("Take profit", value=float(t["take_profit"] or 0), format="%.6f")
        rationale = st.text_area("Tesis", value=t["rationale"] or "")
        why = st.text_input("Motivo del cambio")
        if st.form_submit_button("Guardar cambios"):
            J.update_fields(t["id"], reason=why, setup=setup, take_profit=tp or None, rationale=rationale)
            st.success("Guardado (el cambio queda en la auditoria)")

    with tabs[5]:
        if t["status"] == "PLANNED":
            px = st.number_input("Precio real de ejecucion", value=float(t["entry_price"]), format="%.6f")
            if st.button("Marcar como ejecutada (OPEN)"):
                J.activate_trade(t["id"], px)
                st.rerun()
        why = st.text_input("Motivo de cancelacion")
        if st.button("Cancelar operacion"):
            J.cancel_trade(t["id"], why)
            st.rerun()


def page_history():
    st.header("🧾 Historial y auditoria")
    df = J.list_trades()
    if len(df) == 0:
        st.info("Sin operaciones.")
        return

    c = st.columns(4)
    status = c[0].multiselect("Estado", ["OPEN", "PLANNED", "CLOSED", "CANCELLED"], default=["OPEN", "PLANNED", "CLOSED"])
    source = c[1].multiselect("Fuente", sorted(df["source"].unique()), default=list(df["source"].unique()))
    symbols = c[2].multiselect("Activo", sorted(df["symbol"].unique()))
    if c[3].button("🔐 Verificar integridad"):
        r = J.verify_integrity()
        (st.success if r["ok"] else st.error)(f"{r['detail']} ({r['checked']} eventos)")

    f = df[df["status"].isin(status) & df["source"].isin(source)]
    if symbols:
        f = f[f["symbol"].isin(symbols)]
    cols = ["id", "source", "symbol", "direction", "status", "entry_time", "entry_price", "stop_initial",
            "exit_time", "exit_price", "r_multiple", "pnl", "setup", "emotion_entry", "followed_plan",
            "mae_r", "mfe_r", "features_status"]
    st.dataframe(fmt_df(f.iloc[::-1], cols), hide_index=True, width="stretch")

    if len(f) == 0:
        return
    labels = [trade_label(t) for _, t in f.iloc[::-1].iterrows()]
    pick = st.selectbox("Ver detalle", labels)
    t = J.get_trade(pick.split(" | ")[0])

    a, b = st.columns([2, 3])
    with a:
        st.subheader(f"{t['symbol']} {t['direction']}")
        info = {k: t[k] for k in ("source", "status", "setup", "timeframes", "rationale", "confidence",
                                  "emotion_entry", "emotion_exit", "followed_plan", "mistakes", "tags",
                                  "lessons", "r_multiple", "pnl", "mae_r", "mfe_r", "holding_hours",
                                  "signal_id", "features_status") if t.get(k) not in (None, "", [])}
        st.json(info)
        if t.get("screenshot") and Path(t["screenshot"]).exists():
            st.image(t["screenshot"])
        if t.get("features"):
            with st.expander("Features de mercado en la entrada"):
                st.json(t["features"])
    with b:
        st.subheader("Linea de tiempo")
        for _, e in J.get_events(t["id"]).iterrows():
            p = e["payload"]
            if "changes" in p:
                det = "; ".join(f"**{k}**: {v['before']} → {v['after']}" for k, v in p["changes"].items())
                if p.get("reason"):
                    det = f"_{p['reason']}_ — " + det
            elif "text" in p:
                det = p["text"]
            else:
                det = f"{p.get('direction', '')} {p.get('symbol', '')} @ {p.get('entry_price', '')}" \
                    if "symbol" in p else json.dumps(p, ensure_ascii=False, default=str)[:200]
            st.markdown(f"`{local_str(e['ts'])}` **{e['event_type']}** · {e['actor']}  \n{det}  \n"
                        f"<small>hash {e['hash'][:16]}</small>", unsafe_allow_html=True)


def page_signals():
    st.header("📡 Senales del sistema")
    c = st.columns(2)
    if c[0].button("Evaluar resultado de senales pendientes"):
        from journal.enrichment import evaluate_signals
        with st.spinner("Descargando datos..."):
            st.info(evaluate_signals(J))
    if c[1].button("Actualizar paper trading (SL/TP)"):
        from paper_trading.trade_monitor import update_paper_trades
        with st.spinner("Revisando..."):
            st.info(f"Cerradas: {update_paper_trades(J, log=lambda *x: None)}")
    s = J.list_signals()
    st.dataframe(perf.signals_summary(s), hide_index=True)
    cols = ["id", "created_at", "source", "symbol", "signal", "probability", "confluence_score",
            "model_probability", "entry", "stop", "tp2", "outcome", "outcome_r", "outcome_bars"]
    st.dataframe(fmt_df(s, [c for c in cols if c in s.columns]), hide_index=True, width="stretch")


def _show_report(path, height=1800):
    import streamlit.components.v1 as components
    html = Path(path).read_text(encoding="utf-8")
    components.html(html, height=height, scrolling=True)
    st.download_button("Descargar reporte HTML", html.encode("utf-8"), file_name=Path(path).name,
                       mime="text/html", key=f"dl_{Path(path).name}")


def page_analyze():
    st.header("🔎 Analizar activo")
    st.caption("Recomendacion combinada: senal tecnica + escenarios probabilisticos (analogos y Monte Carlo) "
               "+ backtesting de 6 estrategias con estadistica avanzada.")
    c = st.columns([2, 2, 1])
    pick = c[0].selectbox("Watchlist", settings.WATCHLIST)
    other = c[1].text_input("u otro ticker")
    symbol = (other or pick).upper().strip()
    if c[2].button("Analizar", type="primary"):
        from core.analyzer import run_analysis
        from reports.asset_report import generate_asset_report
        with st.spinner(f"Analizando {symbol} (indicadores, escenarios, backtests)..."):
            try:
                a = run_analysis(symbol)
            except Exception as e:  # noqa: BLE001
                show_error(e)
                return
            path = generate_asset_report(a)
        sid = J.log_signal(a)
        st.session_state["last_analysis"] = {
            "symbol": a["symbol"], "signal": a["signal"], "probability": a["probability"],
            "trade_plan": a["trade_plan"], "factors": a["factors"], "interval": a["interval"],
            "recommendation": a["recommendation"], "signal_id": sid, "report": str(path),
        }

    a = st.session_state.get("last_analysis")
    if not a:
        return
    rec, p = a["recommendation"], a["trade_plan"]
    c = st.columns(5)
    c[0].metric("Recomendacion", rec["action"])
    c[1].metric("Decision Score", f"{rec.get('score') or 0:.0f}/100", rec.get("verdict"))
    c[2].metric("P(TP2 antes que stop)", f"{(rec.get('p_tp2') or 0) * 100:.1f}%")
    c[3].metric("Valor esperado", f"{rec.get('ev_net_r') or 0:+.2f} R")
    c[4].metric("Riesgo sugerido", f"{rec['risk_pct']:.2f}%", f"${rec.get('risk_amount', 0):,.0f}")
    for r in rec["reasons"]:
        st.markdown(f"- {r}")
    st.caption(f"Senal registrada: {a['signal_id'][:8]}")
    if p["direction"] in ("LONG", "SHORT") and st.button("📝 Registrar una operacion con este plan"):
        st.session_state["prefill"] = {
            "symbol": a["symbol"], "direction": p["direction"], "entry": p["entry"], "stop": p["stop"],
            "tp": p["tp2"], "signal_id": a["signal_id"], "interval": a["interval"],
            "rationale": f"Senal {a['signal']} · {rec['action']} (score {rec.get('score')}). " + ", ".join(a["factors"]),
        }
        st.info("Listo: ve a **➕ Registrar operacion** (los datos ya estan cargados).")
    if Path(a["report"]).exists():
        st.divider()
        _show_report(a["report"])


def page_scanner():
    st.header("🎯 Escaner de oportunidades")
    st.caption(f"Analiza toda la watchlist ({', '.join(settings.WATCHLIST)}) y la ordena por Decision Score.")
    bt = st.checkbox("Incluir backtesting de 6 estrategias por activo (mas lento)", value=False)
    if st.button("Escanear ahora", type="primary"):
        from analytics.scanner import scan
        from reports.scanner_report import generate_scanner_report
        bar = st.progress(0.0)
        res = scan(with_backtest=bt, log=lambda *x: None,
                   progress=lambda i, n, s: bar.progress(min(1.0, i / max(n, 1)), text=f"{s}"))
        for a in res["analyses"].values():
            J.log_signal(a)
        path = generate_scanner_report(res)
        st.session_state["last_scan"] = str(path)
        if res["errors"]:
            st.warning(res["errors"])
    if st.session_state.get("last_scan") and Path(st.session_state["last_scan"]).exists():
        _show_report(st.session_state["last_scan"], height=1700)


def page_study():
    st.header("📚 Estudio multi-activo")
    st.caption(f"Las 6 estrategias sobre los {len(settings.WATCHLIST)} activos del universo: que funciona de forma "
               "consistente, en que clase de activo, con estadistica agregada sobre miles de operaciones.")
    c = st.columns(2)
    if c[0].button("Ejecutar estudio", type="primary"):
        from analytics.universe_study import universe_study
        from reports.study_report import generate_study_report
        bar = st.progress(0.0)
        res = universe_study(log=lambda *x: None,
                             progress=lambda i, n, s: bar.progress(min(1.0, i / max(n, 1)), text=s))
        st.session_state["last_study"] = str(generate_study_report(res))
        st.success(f"{len(res['trades']):,} operaciones simuladas en {len(res['symbols'])} activos")
    if c[1].button("Actualizar datos del universo"):
        from data.cache import prefetch
        bar = st.progress(0.0)
        info = prefetch(settings.WATCHLIST, progress=lambda i, n, s: bar.progress(min(1.0, i / max(n, 1)), text=s),
                        log=lambda *x: None)
        st.info(f"Descargados {len(info['ok'])} · frescos {len(info['cached'])} · fallidos {len(info['failed'])}")
    if st.session_state.get("last_study") and Path(st.session_state["last_study"]).exists():
        _show_report(st.session_state["last_study"], height=2000)


def page_backtest():
    st.header("🧪 Backtesting profesional")
    st.caption("6 estrategias sobre los mismos datos, costes reales, IC95, p-valor, Deflated Sharpe, "
               "Monte Carlo, walk-forward, regimenes y sensibilidad de parametros.")
    c = st.columns([2, 2, 1])
    pick = c[0].selectbox("Activo", settings.WATCHLIST, key="bt_pick")
    other = c[1].text_input("u otro ticker", key="bt_other")
    symbol = (other or pick).upper().strip()
    if c[2].button("Ejecutar", type="primary"):
        from backtesting.engine import full_research
        from data.cache import get_data
        with st.spinner("Simulando..."):
            try:
                r = full_research(get_data(symbol), symbol=symbol)
            except Exception as e:  # noqa: BLE001
                show_error(e)
                return
        st.session_state["bt"] = r
    r = st.session_state.get("bt")
    if not r:
        return
    s = r["stats"]
    st.subheader(f"{r['symbol']} · mejor: {r['best'].name} — {s.get('verdict')}")
    c = st.columns(6)
    c[0].metric("Trades", s.get("trades"))
    c[1].metric("Expectativa", f"{s.get('expectancy_r', 0):+.3f} R")
    c[2].metric("p-valor", s.get("p_value"))
    c[3].metric("Deflated Sharpe", f"{(s.get('dsr') or 0) * 100:.1f}%")
    c[4].metric("CAGR", f"{s.get('cagr_pct', 0):.2f}%", f"B&H {r['benchmark'][1].get('cagr_pct', 0):.1f}%")
    c[5].metric("Max DD", f"{s.get('max_drawdown_pct', 0):.2f}%")
    st.dataframe(r["table"], hide_index=True, width="stretch")
    from reports import asset_report as AR
    a, b = st.columns(2)
    a.markdown(AR.chart_equity_compare(r), unsafe_allow_html=True)
    b.markdown(AR.chart_monte_carlo(r), unsafe_allow_html=True)
    a, b = st.columns(2)
    a.markdown(AR.chart_segments(r), unsafe_allow_html=True)
    b.markdown(AR.chart_heatmap(r), unsafe_allow_html=True)
    if r.get("ruin_table") is not None:
        st.subheader("Riesgo de ruina segun % por operacion")
        st.dataframe(r["ruin_table"], hide_index=True, width="stretch")
    st.subheader("Operaciones del backtest")
    st.dataframe(r["best"].trades, hide_index=True, width="stretch")


def page_ai():
    st.header("🤖 Entrenar la IA con tu historial")
    trades = J.list_trades()
    closed = trades[trades["status"] == "CLOSED"] if len(trades) else trades
    ok = int((closed["features_status"] == "OK").sum()) if len(closed) else 0
    c = st.columns(3)
    c[0].metric("Operaciones cerradas", len(closed))
    c[1].metric("Con features (usables)", ok)
    c[2].metric("Senales evaluadas", int(J.list_signals()["outcome"].isin(["WIN", "LOSS", "TIMEOUT"]).sum()))

    if st.button("1) Enriquecer operaciones pendientes"):
        from journal.enrichment import enrich_pending
        with st.spinner("Calculando features y MAE/MFE..."):
            st.write(enrich_pending(J) or "Nada pendiente")

    include = st.checkbox("Incluir muestras historicas del mercado", value=True)
    syms = st.multiselect("Activos para muestras de mercado", settings.WATCHLIST, default=settings.WATCHLIST)
    if st.button("2) Construir dataset y entrenar", type="primary"):
        from ml.dataset import build_dataset, save_dataset
        from ml.model import train_model
        logs = []
        with st.spinner("Construyendo dataset..."):
            ds = build_dataset(J, symbols=syms, include_market=include, log=logs.append)
        st.text("\n".join(logs))
        if len(ds) == 0:
            show_error("Dataset vacio")
            return
        path, meta = save_dataset(ds)
        st.success(f"Dataset: {path} ({meta['rows']} filas)")
        st.download_button("Descargar dataset CSV", Path(path).read_bytes(), file_name=Path(path).name)
        try:
            with st.spinner("Entrenando..."):
                train_model(ds)
        except ValueError as e:
            show_error(e)

    card_path = settings.MODELS_DIR / "model_card.json"
    if card_path.exists():
        card = json.loads(card_path.read_text(encoding="utf-8"))
        st.subheader(f"Modelo actual (entrenado {card['trained_at']})")
        for w in card.get("warnings", []):
            st.warning(w)
        st.dataframe(pd.DataFrame(card["metrics"]).T, width="stretch")
        if card.get("importance"):
            imp = pd.DataFrame(card["importance"]).set_index("feature")["importance"]
            st.bar_chart(imp)


def page_io():
    st.header("⇅ Importar / Exportar")
    st.markdown("Columnas minimas del CSV: `symbol, direction (LONG/SHORT/BUY/SELL), entry_price, stop, quantity`. "
                "Opcionales: `entry_time, exit_time, exit_price, take_profit, fees, setup, notes, broker_ref`.")
    up = st.file_uploader("CSV de operaciones", type=["csv"])
    if up is not None and st.button("Importar"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as fh:
            fh.write(up.getvalue())
        r = J.import_trades_csv(fh.name)
        st.success(f"Importadas {r['imported']} | duplicadas {r['skipped']}")
        for e in r["errors"][:20]:
            st.warning(e)
    st.divider()
    if st.button("Exportar todo a CSV"):
        for k, p in J.export_csv().items():
            st.download_button(f"Descargar {k}", Path(p).read_bytes(), file_name=Path(p).name, key=k)


PAGES = {
    "📊 Panel": page_panel,
    "➕ Registrar operacion": page_register,
    "🛠 Gestionar abiertas": page_manage,
    "🧾 Historial y auditoria": page_history,
    "📡 Senales": page_signals,
    "🔎 Analizar": page_analyze,
    "🎯 Escaner": page_scanner,
    "🧪 Backtesting Pro": page_backtest,
    "📚 Estudio multi-activo": page_study,
    "🤖 IA": page_ai,
    "⇅ Importar / Exportar": page_io,
}

with st.sidebar:
    st.title("QuantSignal AI")
    page = st.radio("Menu", list(PAGES), label_visibility="collapsed")
    st.caption(f"Bitacora: {settings.DB_PATH.name} · motor {settings.ENGINE_VERSION}")

try:
    PAGES[page]()
finally:
    J.close()
