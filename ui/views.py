"""Vistas de consola de los resultados (analisis, escenarios, backtest, escaner)."""

import pandas as pd

from config import settings
from ui import console as C


def _p(v, dec=1):
    return C.GRAY + "-" + C.RESET if v is None else f"{v * 100:.{dec}f}%"


def print_recommendation(a):
    rec = a["recommendation"]
    last = a["df"].iloc[-1]
    C.banner(f"{a['symbol']}  ·  {rec['action']}",
             f"vela {pd.Timestamp(a['candle_time']).date()} · cierre {last['Close']:,.4f} · motor {a['engine_version']}")
    if a.get("incomplete_dropped"):
        C.bullet(f"Se ignoro la vela en curso ({a['incomplete_dropped']}) porque aun no cierra.", "warn")
    C.section("Recomendacion")
    print("  " + C.verdict_badge(rec["action"]) + "  " + C.verdict_badge(rec.get("verdict", "-"))
          + ("  " + C.verdict_badge("senal " + rec["consistency"]) if rec.get("consistency") else ""))
    print("  Decision Score  " + C.score_bar(rec.get("score")))
    C.kv([
        ("P(TP2 antes SL)", _p(rec.get("p_tp2"))),
        ("Valor esperado", C.colored(rec.get("ev_net_r"), C.fmt_num(rec.get("ev_net_r"), 2, sign=True) + " R")),
        ("Riesgo sugerido", f"{rec['risk_pct']:.2f}%  (${rec.get('risk_amount', 0):,.2f})"),
        ("Modelo IA", _p(a.get("model_probability")) if a.get("model_probability") is not None else "sin modelo"),
    ])
    print()
    for r in rec["reasons"]:
        C.bullet(r)


def print_plan(a):
    plan = a["trade_plan"]
    sc = a.get("scenarios")
    C.section(f"Plan tecnico {plan['plan_side']}" + (" (referencia: senal ESPERAR)" if plan["direction"] == "NONE" else ""))
    e = sc["directions"][plan["plan_side"]] if sc else None
    rows = [{"nivel": "Entrada", "precio": plan["entry"], "dist_%": 0.0, "P(tocar antes SL)": None},
            {"nivel": "Stop", "precio": plan["stop"], "dist_%": (plan["stop"] / plan["entry"] - 1) * 100, "P(tocar antes SL)": None}]
    for k, name in enumerate(("TP1", "TP2", "TP3")):
        rows.append({"nivel": name, "precio": plan[name.lower()],
                     "dist_%": (plan[name.lower()] / plan["entry"] - 1) * 100,
                     "P(tocar antes SL)": e["targets"][k]["p_final"] if e else None})
    C.table(rows, formats={"precio": lambda v: f"{v:,.4f}", "dist_%": lambda v: C.fmt_num(v, 2, sign=True) + "%",
                           "P(tocar antes SL)": lambda v: _p(v)})
    pos = a.get("position")
    if pos:
        print(f"\n  Posicion con riesgo {pos['risk_percent']}%: {C.BOLD}{pos['position_size']:,.6f}{C.RESET} unidades "
              f"(nocional ${pos['notional']:,.2f}, riesgo ${pos['risk_amount']:,.2f})")


def print_scenarios(sc):
    if not sc:
        return
    C.section(f"Escenarios · {sc['n_analogs']} casos de {sc.get('n_assets', 1)} activos "
              f"({sc.get('n_effective', sc['n_analogs'])} semanas indep.) · volatilidad x{sc['vol_scale']:.2f}")
    rows = []
    for d, e in sc["directions"].items():
        rows.append({"dir": d, "veredicto": e["verdict"], "score": e["score"],
                     "P(TP1)": e["targets"][0]["p_final"], "P(TP2)": e["p_main"],
                     "azar": e["p_main"] - e["edge_main"], "ventaja": e["edge_main"],
                     "EV neto": e["ev_net_r"], "1/2 Kelly": e["half_kelly_pct"]})
    C.table(rows, formats={
        "veredicto": C.verdict_badge, "P(TP1)": _p, "P(TP2)": _p, "azar": _p,
        "ventaja": lambda v: C.colored(v, C.fmt_num(v * 100, 1, sign=True) + " pp"),
        "EV neto": lambda v: C.colored(v, C.fmt_num(v, 3, sign=True) + " R"),
        "1/2 Kelly": lambda v: f"{v:.2f}%", "score": lambda v: f"{v:.0f}"})
    fw = sc["forward"]
    if "analogos_p_sube" in fw:
        print()
        for _, r in fw.iterrows():
            print(f"  A {int(r['horizonte']):>2} velas: analogos subieron {r['analogos_p_sube'] * 100:.0f}% de las veces, "
                  f"mediana {C.colored(r['analogos_mediana_%'], C.fmt_num(r['analogos_mediana_%'], 2, sign=True) + '%')} "
                  f"(rango p10 {r['analogos_p10_%']:+.1f}% / p90 {r['analogos_p90_%']:+.1f}%)")


def print_research(r, show_table=True):
    if not r:
        return
    s = r["stats"]
    if show_table:
        C.section("Backtesting profesional: comparacion de estrategias")
        cols = ["estrategia", "trades", "win_rate", "expectancy_r", "exp_ci_low", "exp_ci_high",
                "profit_factor", "p_value", "dsr", "cagr_pct", "max_dd_pct", "veredicto"]
        C.table(r["table"], columns=cols,
                headers=["Estrategia", "Ops", "Win%", "E[R]", "IC95 bajo", "IC95 alto", "PF", "p", "DSR", "CAGR%", "MaxDD%", "Veredicto"],
                formats={"expectancy_r": lambda v: C.colored(v, C.fmt_num(v, 3, sign=True)),
                         "veredicto": C.verdict_badge, "dsr": _p,
                         "p_value": lambda v: C.fmt_num(v, 4)})
        b = r["benchmark"][1]
        print(f"\n  Buy & Hold: retorno {b.get('total_return_pct', 0):+.1f}% · CAGR {b.get('cagr_pct', 0):+.1f}% · "
              f"Sharpe {b.get('sharpe') or 0:.2f} · MaxDD {b.get('max_drawdown_pct', 0):.1f}%")
    C.section(f"Mejor estrategia: {r['best'].name}")
    ci = s.get("expectancy_ci") or (None, None)
    C.kv([
        ("Operaciones", f"{s.get('trades', 0)} ({s.get('long_trades', 0)}L/{s.get('short_trades', 0)}S)"),
        ("Veredicto", C.verdict_badge(s.get("verdict", "-"))),
        ("Expectativa", C.colored(s.get("expectancy_r"), C.fmt_num(s.get("expectancy_r"), 3, sign=True) + " R")
         + f"  IC95 [{C.fmt_num(ci[0], 2)}, {C.fmt_num(ci[1], 2)}]"),
        ("Win rate", f"{C.fmt_num(s.get('win_rate'), 1)}%  IC95 {s.get('win_rate_ci')}"),
        ("Profit factor", C.fmt_num(s.get("profit_factor"), 2)),
        ("p-valor / DSR", f"{C.fmt_num(s.get('p_value'), 4)} / {_p(s.get('dsr'))}"),
        ("CAGR / Sharpe", f"{C.fmt_num(s.get('cagr_pct'), 2)}% / {C.fmt_num(s.get('sharpe'), 2)}"),
        ("Sortino / Calmar", f"{C.fmt_num(s.get('sortino'), 2)} / {C.fmt_num(s.get('calmar'), 2)}"),
        ("Max drawdown", f"{C.fmt_num(s.get('max_drawdown_pct'), 2)}%"),
        ("SQN", C.fmt_num(s.get("sqn"), 2)),
        ("Estabilidad", f"{C.fmt_num(r.get('stability'), 0)}% segmentos +"),
        ("Robustez params", f"{r.get('grid_positive_pct', 0):.0f}% combinaciones +"),
    ])
    mc = r.get("monte_carlo")
    if mc:
        print(f"\n  Monte Carlo ({mc['n_sims']:,} sims, riesgo {mc['risk_pct']}%): retorno P5 {mc['final_return_pct'][5]:+.1f}% · "
              f"P50 {mc['final_return_pct'][50]:+.1f}% · P95 {mc['final_return_pct'][95]:+.1f}% | "
              f"DD P50 {mc['max_drawdown_pct'][50]:.1f}% · P95 {mc['max_drawdown_pct'][95]:.1f}% | "
              f"P(perdida) {mc['prob_loss'] * 100:.1f}%")


def print_scan(result):
    t = result["table"]
    C.section("Ranking de oportunidades")
    C.table(t, columns=["rank", "activo", "accion", "score", "veredicto", "p_tp2", "ventaja_pp", "ev_neto_r",
                        "riesgo_%", "senal_tecnica", "mejor_estrategia", "veredicto_backtest"],
            headers=["#", "Activo", "Accion", "Score", "Veredicto", "P(TP2)", "Ventaja", "EV R", "Riesgo%",
                     "Senal", "Mejor estrategia", "Backtest"],
            formats={"veredicto": C.verdict_badge, "p_tp2": _p, "score": lambda v: f"{v:.0f}",
                     "ventaja_pp": lambda v: C.colored(v, C.fmt_num(v, 1, sign=True)),
                     "ev_neto_r": lambda v: C.colored(v, C.fmt_num(v, 3, sign=True)),
                     "veredicto_backtest": lambda v: str(v)[:26]})
    for k, v in (result.get("errors") or {}).items():
        C.bullet(f"{k}: {v}", "bad")


def status_line(journal):
    try:
        open_n = len(journal.list_trades(status=["OPEN", "PLANNED"]))
        closed = journal.list_trades(status="CLOSED")
        sig_n = len(journal.list_signals())
    except Exception:  # noqa: BLE001
        open_n, closed, sig_n = 0, [], 0
    model = "sin modelo"
    card = settings.MODELS_DIR / "model_card.json"
    if card.exists():
        import json
        try:
            model = "modelo " + json.loads(card.read_text(encoding="utf-8"))["trained_at"][:10]
        except (ValueError, KeyError):
            pass
    return (f"Capital ${settings.ACCOUNT_SIZE:,.0f} · riesgo {settings.RISK_PERCENT}% · {settings.INTERVAL}/{settings.PERIOD} · "
            f"{open_n} abiertas · {len(closed)} cerradas · {sig_n} senales · {model}")
