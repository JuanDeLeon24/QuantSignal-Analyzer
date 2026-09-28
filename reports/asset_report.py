"""
Reporte de investigacion por activo (HTML autocontenido):
resumen ejecutivo, escenarios y probabilidades del presente, contexto
tecnico, backtesting profesional con estadistica avanzada y metodologia.
"""

from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from config import settings
from reports import theme as T


# =========================================================
# GRAFICAS
# =========================================================

def chart_price_cone(a):
    d = a["prepared"].tail(160)
    sc = a["scenarios"]
    plan = a["trade_plan"]
    fig, ax = plt.subplots(figsize=(11, 4.4))
    x = np.arange(len(d))
    ax.plot(x, d["Close"].values, color=T.BLUE, lw=1.8, label="Cierre")
    ax.plot(x, d["f_ema_50"].values, color=T.MUTED, lw=1, ls="--", label="EMA 50")
    ax.plot(x, d["f_ema_200"].values, color=T.INK2, lw=1, ls=":", label="EMA 200")
    if sc:
        cf = sc["cone_full"]
        n = len(cf[50])
        fx = np.arange(len(d) - 1, len(d) - 1 + n + 1)
        last = d["Close"].iloc[-1]
        def ext(v):
            return np.r_[last, v]
        ax.fill_between(fx, ext(cf[5]), ext(cf[95]), color=T.BLUE, alpha=0.10, lw=0, label="Cono 5-95% (aleatorio)")
        ax.fill_between(fx, ext(cf[25]), ext(cf[75]), color=T.BLUE, alpha=0.20, lw=0, label="Cono 25-75%")
        ax.plot(fx, ext(cf[50]), color=T.BLUE, lw=1, ls="--")
    xmax = len(d) + (len(sc["cone_full"][50]) if sc else 0)
    levels = [("Entrada", plan["entry"], T.INK2), ("Stop", plan["stop"], T.CRIT),
              ("TP1", plan["tp1"], T.GOOD), ("TP2", plan["tp2"], T.GOOD), ("TP3", plan["tp3"], T.GOOD)]
    for name, val, col in levels:
        ax.axhline(val, color=col, lw=0.9, ls="-" if name in ("Entrada", "Stop") else "--", alpha=0.8)
        ax.text(xmax + 0.5, val, f" {name} {val:,.4g}", va="center", fontsize=8, color=T.INK2)
    ax.set_xlim(0, xmax + 1)
    ticks = np.linspace(0, len(d) - 1, 6).astype(int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(d["Date"].iloc[i]).strftime("%Y-%m-%d") for i in ticks])
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=5)
    ax.set_title(f"{a['symbol']} · precio, niveles del plan y cono de escenarios a {len(sc['cone_full'][50]) if sc else 0} velas")
    return T.img(fig, "Precio y cono de escenarios")


def chart_probabilities(direction_eval):
    t = pd.DataFrame(direction_eval["targets"])
    fig, ax = plt.subplots(figsize=(6, 3.4))
    x = np.arange(len(t))
    w = 0.26
    series = [("p_base_aleatoria", "Base aleatoria", T.ORANGE), ("p_analogos", "Analogos", T.AQUA),
              ("p_final", "Final (combinada)", T.BLUE)]
    for k, (col, label, c) in enumerate(series):
        vals = t[col].fillna(0).values * 100
        bars = ax.bar(x + (k - 1) * w, vals, w - 0.03, color=c, label=label)
        if col == "p_final":
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.0f}%", ha="center", fontsize=8, color=T.INK2)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{o}\n{p:,.4g}" for o, p in zip(t["objetivo"], t["precio"])])
    ax.set_ylabel("% de tocar antes que el stop")
    ax.legend(loc="upper right")
    ax.set_title(f"{direction_eval['direction']}: probabilidad por objetivo")
    return T.img(fig, "Probabilidades por objetivo")


def chart_analog_hist(sc):
    r = sc.get("analog_returns_20")
    if r is None or len(r) == 0:
        return ""
    fig, ax = plt.subplots(figsize=(11, 3.2))
    r = np.asarray(r) * 100
    edges = np.histogram_bin_edges(r, bins=20)
    edges = np.unique(np.r_[edges[edges < 0], 0.0, edges[edges > 0]])
    ax.hist(r[r >= 0], bins=edges, color=T.BLUE, label="Suben", edgecolor=T.SURFACE, linewidth=1)
    ax.hist(r[r < 0], bins=edges, color=T.ORANGE, label="Bajan", edgecolor=T.SURFACE, linewidth=1)
    ax.axvline(0, color=T.INK2, lw=1)
    ax.axvline(np.median(r), color=T.INK, lw=1, ls="--", label=f"Mediana {np.median(r):+.1f}%")
    ax.set_xlabel("Retorno a 20 velas (%)")
    ax.legend()
    ax.set_title("Que paso despues en situaciones parecidas")
    return T.img(fig, "Histograma de analogos")


def chart_equity_compare(research):
    fig, ax = plt.subplots(figsize=(11, 4))
    bench_eq = research["benchmark"][0]
    ax.plot(bench_eq.index, bench_eq.values, color=T.ORANGE, lw=1.6, label="Buy & Hold")
    best_key = research["key"]
    for k, res in research["results"].items():
        eq = res.daily_equity()
        if k == best_key:
            continue
        ax.plot(eq.index, eq.values, color=T.AXIS, lw=0.9)
    eq = research["best"].daily_equity()
    ax.plot(eq.index, eq.values, color=T.BLUE, lw=2.2, label=f"{research['best'].name} (mejor)")
    ax.plot([], [], color=T.AXIS, lw=0.9, label="Otras estrategias")
    ax.set_yscale("log")
    ax.set_ylabel("Capital (escala log)")
    ax.legend(loc="upper left")
    ax.set_title(f"Curvas de capital (riesgo {research['best'].cfg.risk_pct}% por operacion) vs Buy & Hold")
    return T.img(fig, "Comparacion de curvas de capital")


def chart_drawdown(research):
    eq = research["best"].daily_equity()
    dd = (eq / eq.cummax() - 1) * 100
    beq = research["benchmark"][0]
    bdd = (beq / beq.cummax() - 1) * 100
    fig, ax = plt.subplots(figsize=(11, 2.6))
    ax.fill_between(bdd.index, bdd.values, 0, color=T.ORANGE, alpha=0.15, lw=0, label="Buy & Hold")
    ax.fill_between(dd.index, dd.values, 0, color=T.BLUE, alpha=0.45, lw=0, label="Estrategia")
    ax.set_ylabel("Drawdown %")
    ax.legend(loc="lower left")
    ax.set_title("Caidas desde maximos")
    return T.img(fig, "Drawdown")


def chart_monte_carlo(research):
    mc = research.get("monte_carlo")
    if not mc:
        return ""
    b = mc["bands"]
    x = np.arange(1, len(b[50]) + 1)
    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.fill_between(x, b[5], b[95], color=T.BLUE, alpha=0.12, lw=0, label="5-95%")
    ax.fill_between(x, b[25], b[75], color=T.BLUE, alpha=0.25, lw=0, label="25-75%")
    ax.plot(x, b[50], color=T.BLUE, lw=1.6, label="Mediana")
    real = research["best"].equity.values
    ax.plot(np.arange(1, len(real) + 1), real, color=T.ORANGE, lw=1.4, label="Secuencia real")
    ax.axhline(research["best"].cfg.initial_equity, color=T.INK2, lw=0.8)
    ax.set_xlabel("Operacion #")
    ax.set_ylabel("Capital")
    ax.legend(loc="upper left")
    ax.set_title(f"Monte Carlo: {mc['n_sims']:,} ordenes posibles de las operaciones")
    return T.img(fig, "Monte Carlo")


def chart_r_distribution(research):
    t = research["best"].trades
    if len(t) == 0:
        return ""
    fig, ax = plt.subplots(figsize=(6, 3.4))
    r = t["r"]
    edges = np.histogram_bin_edges(r, bins=24)
    edges = np.unique(np.r_[edges[edges < 0], 0.0, edges[edges > 0]])
    ax.hist(r[r > 0], bins=edges, color=T.BLUE, label="Ganadoras", edgecolor=T.SURFACE, linewidth=1)
    ax.hist(r[r <= 0], bins=edges, color=T.ORANGE, label="Perdedoras", edgecolor=T.SURFACE, linewidth=1)
    ax.axvline(r.mean(), color=T.INK, ls="--", lw=1, label=f"Media {r.mean():+.2f} R")
    ax.set_xlabel("Resultado por operacion (R, neto de costes)")
    ax.legend()
    ax.set_title("Distribucion de resultados")
    return T.img(fig, "Distribucion de R")


def chart_heatmap(research):
    p = research.get("grid_pivot")
    if p is None or p.empty:
        return ""
    fig, ax = plt.subplots(figsize=(6, 3.6))
    vals = p.values.astype(float)
    lim = max(0.05, np.nanmax(np.abs(vals)))
    cmap = LinearSegmentedColormap.from_list("div", [T.RED_S, "#f0efec", T.BLUE])
    im = ax.imshow(vals, cmap=cmap, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    ax.set_xticks(range(len(p.columns)))
    ax.set_xticklabels([f"{c:g}R" for c in p.columns])
    ax.set_yticks(range(len(p.index)))
    ax.set_yticklabels([f"{i:g} ATR" for i in p.index])
    ax.set_xlabel("Objetivo")
    ax.set_ylabel("Stop")
    ax.grid(False)
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            if np.isfinite(vals[i, j]):
                ax.text(j, i, f"{vals[i, j]:+.2f}", ha="center", va="center", fontsize=8.5, color=T.INK)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Expectativa (R)")
    ax.set_title("Sensibilidad de parametros")
    return T.img(fig, "Mapa de sensibilidad")


def chart_segments(research):
    s = research.get("segments")
    if s is None or len(s) == 0:
        return ""
    fig, ax = plt.subplots(figsize=(6, 3.2))
    cols = [T.BLUE if v > 0 else T.ORANGE for v in s["expectancy_r"]]
    ax.bar(s["segmento"].astype(str), s["expectancy_r"], color=cols, width=0.6)
    ax.axhline(0, color=T.INK2, lw=0.8)
    for i, (v, n) in enumerate(zip(s["expectancy_r"], s["trades"])):
        ax.text(i, v, f"{v:+.2f}R\n{n} ops", ha="center", va="bottom" if v >= 0 else "top", fontsize=8, color=T.INK2)
    ax.margins(y=0.25)
    ax.set_xlabel("Segmento temporal")
    ax.set_ylabel("Expectativa (R)")
    ax.set_title("Estabilidad en el tiempo (walk-forward)")
    return T.img(fig, "Estabilidad walk-forward")


# =========================================================
# SECCIONES
# =========================================================

def _pct(v, dec=1):
    return "–" if v is None else f"{v * 100:.{dec}f}%"


def section_summary(a):
    rec = a["recommendation"]
    sc = a["scenarios"]
    plan = a["trade_plan"]
    best = sc["directions"][rec["direction"]] if sc else None
    last = a["df"].iloc[-1]

    left = (f'<div class="card"><div class="muted">Recomendacion</div>'
            f'<div class="verdict">{T.esc(rec["action"])}</div>'
            f'{T.badge(rec.get("verdict", "-"))} '
            + (T.badge("Senal tecnica y escenarios " + rec["consistency"].lower()) if rec.get("consistency") else "")
            + '<ul class="reasons">' + "".join(f"<li>{T.esc(r)}</li>" for r in rec["reasons"]) + "</ul></div>")
    right = (f'<div class="card">{T.gauge(rec.get("score"))}'
             '<div class="grid" style="margin-top:14px">'
             + T.kpi("P(TP2 antes que stop)", _pct(rec.get("p_tp2")),
                     f'azar: {_pct(best["p_main"] - best["edge_main"]) if best else "–"}')
             + T.kpi("Valor esperado", T.fmt(rec.get("ev_net_r"), 2, sign=True) + " R", "neto de costes",
                     T.tone(rec.get("ev_net_r")))
             + T.kpi("Riesgo sugerido", f'{rec["risk_pct"]:.2f}%', f'${rec.get("risk_amount", 0):,.2f} de ${settings.ACCOUNT_SIZE:,.0f}')
             + T.kpi("Medio Kelly", f'{best["half_kelly_pct"]:.2f}%' if best else "–", f"tope {settings.MAX_RISK_PERCENT}%")
             + "</div></div>")
    kpis = "".join([
        T.kpi("Ultimo cierre", T.fmt(last["Close"], 4), T.fmt_date(last["Date"])),
        T.kpi("Senal tecnica", T.esc(a["signal"]), f'score {a["score"]}/100'),
        T.kpi("Confluencia LONG", f'{a["directional"]["LONG"]["score"]}/100'),
        T.kpi("Confluencia SHORT", f'{a["directional"]["SHORT"]["score"]}/100'),
        T.kpi("Modelo IA P(exito)", _pct(a.get("model_probability")) if a.get("model_probability") is not None else "sin modelo"),
        T.kpi("ATR (volatilidad)", T.fmt(a["indicators"]["ATR"], 4), f'{a["indicators"]["ATR"] / last["Close"] * 100:.2f}% del precio'),
    ])
    note = ""
    if a.get("incomplete_dropped"):
        note = f'<p class="note">Se ignoro la vela en curso ({T.esc(a["incomplete_dropped"])}) porque aun no ha cerrado.</p>'
    plan_tbl = pd.DataFrame([
        {"nivel": "Entrada", "precio": plan["entry"], "distancia_%": 0.0},
        {"nivel": "Stop", "precio": plan["stop"], "distancia_%": (plan["stop"] / plan["entry"] - 1) * 100},
        {"nivel": "TP1 (1R)", "precio": plan["tp1"], "distancia_%": (plan["tp1"] / plan["entry"] - 1) * 100},
        {"nivel": "TP2 (2R)", "precio": plan["tp2"], "distancia_%": (plan["tp2"] / plan["entry"] - 1) * 100},
        {"nivel": "TP3 (2.5R)", "precio": plan["tp3"], "distancia_%": (plan["tp3"] / plan["entry"] - 1) * 100},
    ])
    return (f'<section id="resumen"><h2>Resumen ejecutivo</h2><div class="hero">{left}{right}</div>'
            f'<div class="grid" style="margin-top:14px">{kpis}</div>{note}'
            f'<div class="two" style="margin-top:14px"><div class="card"><h3>Plan tecnico ({T.esc(plan["plan_side"])})</h3>'
            f'{T.table(plan_tbl, formats={"precio": lambda v: T.fmt(v, 4), "distancia_%": lambda v: T.fmt(v, 2, sign=True) + "%"})}</div>'
            f'<div class="card">{chart_probabilities(best) if best else ""}</div></div></section>')


def section_scenarios(a):
    sc = a["scenarios"]
    if not sc:
        return ""
    rows = []
    for d_, e in sc["directions"].items():
        rows.append({
            "direccion": d_, "veredicto": e["verdict"], "score": e["score"],
            "P(TP1)": e["targets"][0]["p_final"], "P(TP2)": e["p_main"],
            "P(TP2) azar": e["p_main"] - e["edge_main"], "ventaja_pp": e["edge_main"] * 100,
            "EV_neto_R": e["ev_net_r"], "analogos": e["n_analogs"],
            "casos_indep": e.get("n_effective"), "activos": e.get("n_assets"),
            "IC95_win_analogos": e["analog_win_ci"], "confluencia": e["confluence"],
            "modelo_IA": e["model_p"],
        })
    comp = pd.DataFrame(rows)
    pct = lambda v: _pct(v)  # noqa: E731
    fwd = sc["forward"].copy()
    price = sc["price"]
    for c in ("aleatorio_p5", "aleatorio_p50", "aleatorio_p95"):
        if c in fwd:
            fwd[c + "_%"] = (fwd[c] / price - 1) * 100
            fwd = fwd.drop(columns=c)
    fwd = fwd.rename(columns={"horizonte": "velas", "analogos_p_sube": "P(sube) analogos",
                              "analogos_mediana_%": "mediana analogos %", "analogos_p10_%": "p10 analogos %",
                              "analogos_p90_%": "p90 analogos %", "aleatorio_p5_%": "p5 aleatorio %",
                              "aleatorio_p50_%": "mediana aleatoria %", "aleatorio_p95_%": "p95 aleatorio %"})
    body = [
        '<section id="escenarios"><h2>Escenarios y probabilidades del presente</h2>',
        '<p class="note">Se comparan dos fuentes: <b>analogos</b> (las '
        f'{sc["n_analogs"]} situaciones historicas mas parecidas a la actual en tendencia, momentum, volatilidad y '
        f'estructura, buscadas en {sc.get("pool_size", 1)} activo(s); aparecen en {sc.get("n_assets", 1)} activos y '
        f'{sc.get("n_effective", sc["n_analogs"])} semanas distintas, que es el numero de casos que se consideran '
        'independientes) y una <b>base aleatoria</b> (Monte Carlo por bootstrap de velas reescalado a la volatilidad '
        f'actual x{sc["vol_scale"]:.2f}, sin tendencia). La probabilidad final contrae los analogos hacia la base '
        'para no sobrerreaccionar con pocas muestras. La <b>ventaja</b> es cuanto mejora la situacion actual sobre el azar.</p>',
        '<div class="card">' + T.table(comp, formats={
            "P(TP1)": pct, "P(TP2)": pct, "P(TP2) azar": pct, "modelo_IA": pct,
            "ventaja_pp": lambda v: T.fmt(v, 1, sign=True), "EV_neto_R": lambda v: T.fmt(v, 3, sign=True),
            "veredicto": T.badge}, tones=["ventaja_pp", "EV_neto_R"]) + "</div>",
        f'<div class="card" style="margin-top:14px">{chart_price_cone(a)}</div>',
        f'<div class="card" style="margin-top:14px">{chart_analog_hist(sc)}</div>',
        '<div class="card" style="margin-top:14px"><h3>Distribucion futura: analogos vs aleatorio</h3>'
        + T.table(fwd, formats={"velas": lambda v: f"{int(v)}", "P(sube) analogos": pct},
                  tones=["mediana analogos %"])
        + '<p class="note">Si la mediana de los analogos se separa claramente de la mediana aleatoria (~0%), '
          'la situacion actual ha tenido historicamente un sesgo direccional.</p></div>',
    ]
    if "analog_table" in sc:
        body.append('<div class="two" style="margin-top:14px"><div class="card"><h3>Situaciones historicas mas parecidas</h3>'
                    + T.table(sc["analog_table"], tones=["ret_20v_%", "R_long", "R_short"]) + "</div>"
                    + '<div class="card"><h3>De que activos vienen los casos</h3>'
                    + T.table(sc.get("analog_assets"), max_rows=25) + "</div></div>")
    body.append("</section>")
    return "".join(body)


def section_technical(a):
    ctx = a["context"]
    rows = pd.DataFrame([
        {"indicador": "Tendencia EMA50/200", "valor": ctx["trend"]},
        {"indicador": "Estructura (HH/HL/LH/LL)", "valor": ctx["market_structure"]},
        {"indicador": "BOS", "valor": ctx["bos"]},
        {"indicador": "CHOCH", "valor": ctx["choch"]},
        {"indicador": "Liquidez", "valor": ctx["liquidity"]},
        {"indicador": "Premium/Discount", "valor": ctx["pd_zone"]},
        {"indicador": "Zona Fibonacci", "valor": ctx["fib_zone"]},
        {"indicador": "Volumen", "valor": ctx["volume_signal"]},
        {"indicador": "Soporte", "valor": T.fmt(ctx["support"], 4)},
        {"indicador": "Resistencia", "valor": T.fmt(ctx["resistance"], 4)},
    ] + [{"indicador": k, "valor": T.fmt(v, 2)} for k, v in a["indicators"].items()])
    fac = []
    for d_ in ("LONG", "SHORT"):
        x = a["directional"][d_]
        fac.append(f'<div class="card"><h3>Confluencia {d_}: {x["score"]}/100</h3>'
                   + "<ul class='reasons checks'>" + "".join(f"<li>✔ {T.esc(f)}</li>" for f in x["factors"])
                   + "".join(f"<li class='muted'>✖ {T.esc(f)}</li>" for f in x["against"]) + "</ul></div>")
    return (f'<section id="tecnico"><h2>Contexto tecnico</h2><div class="two">'
            f'<div class="card">{T.table(rows)}</div><div class="stack">{"".join(fac)}</div></div></section>')


def section_backtest(a):
    r = a.get("research")
    if not r:
        return ""
    s = r["stats"]
    bench = r["benchmark"][1]
    table = r["table"].copy()
    fmt_ci = lambda row: f'{T.fmt(row["exp_ci_low"], 2, sign=True)} a {T.fmt(row["exp_ci_high"], 2, sign=True)}'  # noqa: E731
    table["IC95_expectativa"] = table.apply(fmt_ci, axis=1)
    table = table[["estrategia", "trades", "win_rate", "expectancy_r", "IC95_expectativa", "profit_factor",
                   "sqn", "p_value", "dsr", "cagr_pct", "sharpe", "max_dd_pct", "veredicto"]]
    ci = s.get("expectancy_ci") or (None, None)
    kp = "".join([
        T.kpi("Operaciones", s.get("trades", 0), f'{s.get("long_trades", 0)} long / {s.get("short_trades", 0)} short'),
        T.kpi("Win rate", T.fmt(s.get("win_rate"), 1) + "%",
              f'IC95 {T.fmt((s.get("win_rate_ci") or (None,))[0], 1)}–{T.fmt((s.get("win_rate_ci") or (None, None))[1], 1)}%'),
        T.kpi("Expectativa", T.fmt(s.get("expectancy_r"), 3, sign=True) + " R",
              f"IC95 {T.fmt(ci[0], 2, sign=True)} a {T.fmt(ci[1], 2, sign=True)}", T.tone(s.get("expectancy_r"))),
        T.kpi("Profit factor", T.fmt(s.get("profit_factor"), 2), f'IC95 {" – ".join(T.fmt(x, 2) for x in (s.get("profit_factor_ci") or (None, None)))}'),
        T.kpi("p-valor (E[R]>0)", T.fmt(s.get("p_value"), 4), "t-test unilateral"),
        T.kpi("Deflated Sharpe", _pct(s.get("dsr")), f'corrige {s.get("n_trials")} pruebas'),
        T.kpi("CAGR", T.fmt(s.get("cagr_pct"), 2) + "%", f'Buy&Hold {T.fmt(bench.get("cagr_pct"), 2)}%', T.tone(s.get("cagr_pct"))),
        T.kpi("Sharpe / Sortino", f'{T.fmt(s.get("sharpe"), 2)} / {T.fmt(s.get("sortino"), 2)}', f'B&H Sharpe {T.fmt(bench.get("sharpe"), 2)}'),
        T.kpi("Max drawdown", T.fmt(s.get("max_drawdown_pct"), 2) + "%", f'B&H {T.fmt(bench.get("max_drawdown_pct"), 1)}%'),
        T.kpi("Calmar / Ulcer", f'{T.fmt(s.get("calmar"), 2)} / {T.fmt(s.get("ulcer_index"), 2)}'),
        T.kpi("SQN", T.fmt(s.get("sqn"), 2), "Van Tharp: >2 bueno, >3 excelente"),
        T.kpi("Estabilidad", (T.fmt(r.get("stability"), 0) + "%") if r.get("stability") is not None else "–", "segmentos con E[R]>0"),
    ])
    mc = r.get("monte_carlo")
    mc_tbl = ""
    if mc:
        mc_df = pd.DataFrame({
            "percentil": ["P5 (malo)", "P25", "P50 (tipico)", "P75", "P95 (bueno)"],
            "retorno_final_%": [mc["final_return_pct"][p] for p in (5, 25, 50, 75, 95)],
            "max_drawdown_%": [mc["max_drawdown_pct"][p] for p in (5, 25, 50, 75, 95)],
        })
        mc_tbl = (T.table(mc_df, tones=["retorno_final_%"])
                  + f'<p class="note">Probabilidad de terminar en perdida: <b>{mc["prob_loss"] * 100:.1f}%</b> · '
                  f'probabilidad de un drawdown ≥ {mc["ruin_threshold_pct"]:.0f}%: <b>{mc["prob_ruin"] * 100:.1f}%</b></p>')
    body = [
        '<section id="backtest"><h2>Backtesting profesional</h2>',
        '<p class="note">Entrada a la apertura de la vela siguiente a la senal, comisiones '
        f'{settings.FEE_PCT * 100:.2f}% y slippage {settings.SLIPPAGE_PCT * 100:.2f}% por lado, stop/objetivo por ATR, '
        'criterio conservador si una vela toca ambos. Todas las estrategias sobre los mismos datos. '
        'El <b>Deflated Sharpe</b> descuenta la suerte de haber elegido la mejor entre muchas pruebas.</p>',
        '<div class="card"><h3>Comparacion de estrategias</h3>'
        + T.table(table, formats={"veredicto": T.badge, "p_value": lambda v: T.fmt(v, 4),
                                  "psr": _pct, "dsr": _pct, "expectancy_r": lambda v: T.fmt(v, 3, sign=True)},
                  tones=["expectancy_r", "cagr_pct"]) + "</div>",
        f'<h3 style="margin-top:18px">Mejor estrategia: {T.esc(r["best"].name)} · {T.badge(s.get("verdict", ""))}</h3>',
        f'<div class="grid">{kp}</div>',
        f'<div class="card" style="margin-top:14px">{chart_equity_compare(r)}{chart_drawdown(r)}</div>',
        '<div class="two" style="margin-top:14px">'
        f'<div class="card">{chart_monte_carlo(r)}{mc_tbl}</div>'
        f'<div class="card">{chart_r_distribution(r)}</div></div>',
        '<div class="two" style="margin-top:14px">'
        f'<div class="card">{chart_segments(r)}{T.table(r.get("segments"), tones=["expectancy_r", "total_r"])}</div>'
        f'<div class="card">{chart_heatmap(r)}<p class="note">{r["grid_positive_pct"]:.0f}% de las combinaciones '
        'tienen expectativa positiva. Una zona amplia en azul indica robustez; un unico punto azul, sobreajuste.</p></div></div>',
    ]
    reg = []
    for title, key in (("Por tendencia", "regime_trend"), ("Por volatilidad", "regime_vol"),
                       ("Por direccion", "by_direction"), ("Por motivo de salida", "by_reason")):
        if r.get(key) is not None and len(r.get(key)):
            reg.append(f'<div class="card"><h3>{title}</h3>{T.table(r[key], tones=["expectancy_r", "total_r"])}</div>')
    if reg:
        body.append('<h3 style="margin-top:18px">Rendimiento por regimen de mercado</h3><div class="two">' + "".join(reg) + "</div>")
    if r.get("ruin_table") is not None and len(r["ruin_table"]):
        body.append('<div class="card" style="margin-top:14px"><h3>Cuanto arriesgar: riesgo de ruina segun % por operacion</h3>'
                    + T.table(r["ruin_table"], tones=["retorno_mediano_%", "retorno_p5_%"]) + "</div>")
    t = r["best"].trades
    if len(t):
        last = t.tail(25).iloc[::-1][["entry_time", "exit_time", "direction", "entry", "exit", "reason", "bars",
                                        "r", "mae_r", "mfe_r", "regime_trend"]]
        body.append('<details><summary>Ultimas 25 operaciones del backtest</summary><div class="card">'
                    + T.table(last, formats={"entry_time": T.fmt_date, "exit_time": T.fmt_date}, tones=["r"])
                    + "</div></details>")
    body.append("</section>")
    return "".join(body)


def section_method():
    return ("<section id='metodo'><h2>Metodologia y limites</h2><div class='card'><ul class='reasons'>"
            "<li><b>Sin mirar al futuro:</b> los swings solo cuentan cuando estan confirmados; las senales usan velas cerradas.</li>"
            "<li><b>R</b> = resultado dividido por el riesgo inicial. 1R = ganaste lo que arriesgabas.</li>"
            "<li><b>IC95</b>: intervalo donde con 95% de confianza esta el valor real (bootstrap / Wilson).</li>"
            "<li><b>p-valor</b>: probabilidad de ver esta expectativa si en realidad fuera cero. &lt;0.05 = significativo.</li>"
            "<li><b>PSR/DSR</b> (Bailey y Lopez de Prado): probabilidad de que el Sharpe real sea positivo, "
            "el DSR ademas penaliza el numero de estrategias y parametros probados.</li>"
            "<li><b>Kelly</b>: fraccion teorica de crecimiento maximo. Se usa la mitad y con tope, porque las "
            "probabilidades son estimaciones.</li>"
            "<li><b>Limites:</b> los analogos asumen que el pasado se parece al futuro; noticias y eventos macro no "
            "estan en el modelo; el backtest no incluye financiamiento, impuestos ni liquidez extrema.</li>"
            "</ul></div></section>")


def generate_asset_report(a, path=None):
    settings.ensure_dirs()
    stamp = datetime.now()
    path = path or settings.REPORTS_DIR / f"analisis_{a['symbol'].replace('/', '_')}_{stamp:%Y%m%d_%H%M}.html"
    toc = ("<nav class='toc'><a href='#resumen'>Resumen</a><a href='#escenarios'>Escenarios</a>"
           "<a href='#tecnico'>Tecnico</a><a href='#backtest'>Backtesting</a><a href='#metodo'>Metodologia</a></nav>")
    header = (f"<header class='top'><div><div class='brand'>QuantSignal AI · Reporte de investigacion</div>"
              f"<h1>{T.esc(a['symbol'])}</h1><div class='meta'>Vela analizada {T.fmt_date(a['candle_time'])} · "
              f"intervalo {T.esc(a['interval'])} · generado {stamp:%Y-%m-%d %H:%M} · motor {T.esc(a['engine_version'])} · "
              f"datos {T.esc(a['data_hash'])}</div></div>{T.badge(a['recommendation']['action'])}</header>")
    body = header + toc + section_summary(a) + section_scenarios(a) + section_technical(a) + section_backtest(a) + section_method()
    path.write_text(T.page(f"{a['symbol']} · QuantSignal AI", body, f"motor {a['engine_version']}"), encoding="utf-8")
    return path
