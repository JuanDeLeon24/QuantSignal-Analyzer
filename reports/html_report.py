"""
Reporte HTML autocontenido de la bitacora (se abre con doble clic,
funciona sin internet). Graficas con matplotlib embebidas en base64.
"""

import base64
import html
import io
import json
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from config import settings  # noqa: E402
from reports import performance as perf  # noqa: E402
from reports import theme as T  # noqa: E402
from analytics import stats as ST  # noqa: E402

EXTRA_CSS = """
.kpi.good .v{color:var(--pos)}.kpi.bad .v{color:var(--neg)}
.badge.ok{color:var(--pos);border-color:var(--pos)}.badge.ko{color:var(--neg);border-color:var(--neg)}
h1{margin-bottom:6px}.two{margin-bottom:14px}
"""


def edge_section(closed):
    """Estadistica avanzada sobre TUS operaciones: tu ventaja es real o suerte?"""
    r = closed["r_multiple"].dropna()
    if len(r) < 5:
        return ("<h2>Tu ventaja es real?</h2><p class='muted'>Se necesitan al menos 5 operaciones cerradas "
                "para la estadistica avanzada (idealmente 30+).</p>")
    s = ST.trade_stats(r)
    mc = ST.monte_carlo(r, settings.RISK_PERCENT, n_sims=4000)
    ruin = ST.risk_of_ruin_table(r, n_sims=2000)
    t_ = closed.assign(r=closed["r_multiple"], entry_time=closed["entry_time"])
    seg = ST.walk_forward_segments(t_, n_segments=min(5, max(2, len(r) // 6)))
    ci = s.get("expectancy_ci") or (None, None)
    kp = "".join([
        T.kpi("Veredicto", T.badge(s["verdict"]), f"{s['trades']} operaciones"),
        T.kpi("Expectativa", T.fmt(s["expectancy_r"], 3, sign=True) + " R",
              f"IC95 {T.fmt(ci[0], 2, sign=True)} a {T.fmt(ci[1], 2, sign=True)}", T.tone(s["expectancy_r"])),
        T.kpi("p-valor", T.fmt(s.get("p_value"), 4), "prob. de que sea suerte"),
        T.kpi("PSR", "–" if s.get("psr") is None else f"{s['psr'] * 100:.1f}%", "P(Sharpe real > 0)"),
        T.kpi("SQN", T.fmt(s.get("sqn"), 2), ">2 bueno · >3 excelente"),
        T.kpi("Kelly", "–" if s.get("kelly") is None else f"{s['kelly'] * 100:.1f}%", "usa como maximo la mitad"),
    ])
    mc_txt = ""
    if mc:
        mc_txt = (f"<p class='note'>Si repitieras estas mismas {len(r)} operaciones en otro orden "
                  f"({mc['n_sims']:,} simulaciones, riesgo {settings.RISK_PERCENT}%): retorno tipico "
                  f"<b>{mc['final_return_pct'][50]:+.1f}%</b> (P5 {mc['final_return_pct'][5]:+.1f}%, "
                  f"P95 {mc['final_return_pct'][95]:+.1f}%), drawdown tipico {mc['max_drawdown_pct'][50]:.1f}% "
                  f"y en el peor 5% de los casos {mc['max_drawdown_pct'][95]:.1f}%. "
                  f"Probabilidad de terminar en perdida: <b>{mc['prob_loss'] * 100:.1f}%</b>.</p>")
    return ("<h2>Tu ventaja es real? (estadistica avanzada)</h2>"
            f"<div class='grid'>{kp}</div>{mc_txt}"
            "<div class='two'>"
            f"<div class='card'><h3>Estabilidad en el tiempo</h3>{T.table(seg, tones=['expectancy_r', 'total_r'])}</div>"
            f"<div class='card'><h3>Cuanto arriesgar por operacion</h3>{T.table(ruin, tones=['retorno_mediano_%', 'retorno_p5_%'])}</div>"
            "</div>")

GREEN, RED, BLUE, GRAY, PURPLE = "#2a78d6", "#eb6834", "#2a78d6", "#898781", "#4a3aa7"


def _img(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return f'<img alt="grafica" src="data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}">'


def _style(ax, title):
    ax.set_title(title, fontsize=11, loc="left")
    ax.grid(True, alpha=0.25)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def _table(df, max_rows=200):
    if df is None or len(df) == 0:
        return '<p class="muted">Sin datos todavia.</p>'
    return df.head(max_rows).to_html(index=False, classes="tbl", border=0, na_rep="-",
                                     float_format=lambda x: f"{x:,.3f}".rstrip("0").rstrip("."))


def _kpi(label, value, suffix="", tone=""):
    v = "-" if value is None else f"{value:,.2f}{suffix}" if isinstance(value, float) else f"{value}{suffix}"
    return f'<div class="kpi {tone}"><div class="v">{html.escape(v)}</div><div class="l">{label}</div></div>'


def chart_equity(eq):
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.6))
    axes[0].plot(eq["exit_time"], eq["equity"], color=GREEN, lw=2)
    _style(axes[0], "Equity ($) - operaciones cerradas")
    axes[1].plot(eq["exit_time"], eq["cum_r"], color=BLUE, lw=2)
    axes[1].axhline(0, color=GRAY, lw=0.8)
    _style(axes[1], "R acumulado")
    fig.autofmt_xdate()
    return _img(fig)


def chart_drawdown(eq):
    fig, ax = plt.subplots(figsize=(12, 2.6))
    ax.fill_between(eq["exit_time"], -eq["drawdown_pct"], 0, color=RED, alpha=0.25)
    ax.plot(eq["exit_time"], -eq["drawdown_pct"], color=RED, lw=1.2)
    _style(ax, "Drawdown (%)")
    fig.autofmt_xdate()
    return _img(fig)


def chart_r_hist(closed):
    fig, ax = plt.subplots(figsize=(6, 3.4))
    r = closed["r_multiple"].dropna()
    ax.hist(r[r > 0], bins=15, color=GREEN, alpha=0.8, label="Ganadoras")
    ax.hist(r[r <= 0], bins=15, color=RED, alpha=0.8, label="Perdedoras")
    ax.axvline(r.mean(), color="black", ls="--", lw=1, label=f"Media {r.mean():.2f}R")
    ax.legend(frameon=False, fontsize=8)
    _style(ax, "Distribucion de resultados (R)")
    return _img(fig)


def chart_mae_mfe(closed):
    d = closed.dropna(subset=["mae_r", "mfe_r"])
    if len(d) == 0:
        return '<p class="muted">MAE/MFE aparece cuando las operaciones estan enriquecidas con datos de mercado.</p>'
    fig, ax = plt.subplots(figsize=(6, 3.4))
    c = [GREEN if x > 0 else RED for x in d["r_multiple"]]
    ax.scatter(d["mae_r"], d["mfe_r"], c=c, alpha=0.8, s=28)
    ax.axvline(1, color=GRAY, ls=":", lw=1)
    ax.set_xlabel("MAE (R): cuanto fue en contra")
    ax.set_ylabel("MFE (R): cuanto fue a favor")
    _style(ax, "Calidad de entradas y salidas")
    return _img(fig)


def chart_bar(df, label_col, value_col, title):
    if df is None or len(df) == 0:
        return ""
    d = df.sort_values(value_col)
    fig, ax = plt.subplots(figsize=(6, max(2.2, 0.38 * len(d) + 0.8)))
    ax.barh(d[label_col].astype(str), d[value_col], color=[GREEN if v > 0 else RED for v in d[value_col]])
    ax.axvline(0, color=GRAY, lw=0.8)
    _style(ax, title)
    return _img(fig)


def _events_table(journal, limit=300):
    ev = journal.get_events()
    if len(ev) == 0:
        return pd.DataFrame()
    ev = ev.tail(limit).iloc[::-1].copy()
    ev["trade"] = ev["trade_id"].str[:8]
    ev["detalle"] = ev["payload"].apply(_describe_payload)
    ev["hash"] = ev["hash"].str[:12]
    return ev[["seq", "ts", "trade", "event_type", "actor", "detalle", "hash"]]


def _describe_payload(p):
    if not isinstance(p, dict):
        return str(p)
    if "changes" in p:
        parts = [f"{k}: {v['before']} -> {v['after']}" for k, v in p["changes"].items()
                 if k not in ("updated_at",)]
        s = "; ".join(parts[:6])
        if p.get("reason"):
            s = f"[{p['reason']}] " + s
        return s[:220]
    if "text" in p:
        return p["text"][:220]
    if "symbol" in p:
        return f"{p.get('direction')} {p.get('symbol')} @ {p.get('entry_price')} SL {p.get('stop_initial')}"
    return json.dumps(p, ensure_ascii=False)[:220]


CSS = """
:root{--bg:#f6f8fa;--card:#fff;--fg:#1f2328;--muted:#57606a;--line:#d0d7de;--g:#1a7f37;--r:#cf222e}
@media (prefers-color-scheme: dark){:root{--bg:#0d1117;--card:#161b22;--fg:#e6edf3;--muted:#8d96a0;--line:#30363d;--g:#3fb950;--r:#f85149}
 img{background:#fff;border-radius:6px}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}
.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.kpi .v{font-size:20px;font-weight:600}.kpi .l{color:var(--muted);font-size:12px}
.kpi.good .v{color:var(--g)}.kpi.bad .v{color:var(--r)}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:16px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;overflow-x:auto}
img{max-width:100%;height:auto}
.tbl{border-collapse:collapse;width:100%;font-size:12.5px}.tbl th,.tbl td{padding:5px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
.tbl th{color:var(--muted);font-weight:600}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600}
.ok{background:#dafbe1;color:#116329}.ko{background:#ffebe9;color:#a40e26}
"""


def generate_html_report(journal, path=None, account_size=None):
    account_size = account_size or settings.ACCOUNT_SIZE
    settings.ensure_dirs()
    path = path or settings.REPORTS_DIR / f"bitacora_{datetime.now():%Y%m%d_%H%M}.html"

    trades = journal.list_trades()
    signals = journal.list_signals()
    closed = perf.closed_trades(trades)
    s = perf.summary(trades, account_size)
    integ = journal.verify_integrity()

    parts = [f"<!doctype html><html lang='es'><head><meta charset='utf-8'>"
             f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>Bitacora QuantSignal</title><style>{T.CSS}{EXTRA_CSS}</style></head><body><div class='wrap'>"]
    parts.append("<h1>QuantSignal AI - Bitacora de operaciones</h1>")
    badge = (f"<span class='badge ok'>Integridad OK - {integ['checked']} eventos verificados</span>"
             if integ["ok"] else
             f"<span class='badge ko'>ALERTA de integridad en evento #{integ['broken_at']}: {integ['detail']}</span>")
    parts.append(f"<p class='muted'>Generado {datetime.now():%Y-%m-%d %H:%M} | "
                 f"{len(trades)} operaciones | {len(signals)} senales | {badge}</p>")

    # KPIs
    if s.get("trades"):
        tone = lambda v: "good" if (v or 0) > 0 else "bad"  # noqa: E731
        parts.append("<div class='grid'>" + "".join([
            _kpi("Operaciones cerradas", s["trades"]),
            _kpi("Win rate", s["win_rate"], "%"),
            _kpi("Profit factor", s["profit_factor"]),
            _kpi("Expectativa", s["expectancy_r"], " R", tone(s["expectancy_r"])),
            _kpi("R total", s["total_r"], " R", tone(s["total_r"])),
            _kpi("PnL total", s["total_pnl"], " $", tone(s["total_pnl"])),
            _kpi("Max drawdown", s["max_drawdown_pct"], "%", "bad" if s["max_drawdown_pct"] > 10 else ""),
            _kpi("Sharpe / trade", s["sharpe_per_trade"]),
            _kpi("Racha perdedora", s["max_loss_streak"]),
            _kpi("Plan respetado", s["plan_adherence_pct"], "%"),
        ]) + "</div>")

        eq = perf.equity_series(trades, account_size)
        parts.append("<h2>Curva de capital</h2><div class='card'>" + chart_equity(eq) + chart_drawdown(eq) + "</div>")
        parts.append(edge_section(closed))
        parts.append("<h2>Distribucion y ejecucion</h2><div class='two'>"
                     f"<div class='card'>{chart_r_hist(closed)}</div>"
                     f"<div class='card'>{chart_mae_mfe(closed)}</div></div>")

        by_setup = perf.breakdown(trades, "setup")
        by_source = perf.breakdown(trades, "source")
        by_symbol = perf.breakdown(trades, "symbol")
        by_emotion = perf.breakdown(trades, "emotion_entry")
        plan = perf.breakdown(trades.assign(plan=trades["followed_plan"].map({1: "Si", 0: "No"})), "plan")
        mistakes = perf.mistakes_breakdown(trades)
        wd, _ = perf.time_breakdown(trades, settings.LOCAL_TZ)

        parts.append("<h2>Que funciona y que no</h2><div class='two'>"
                     f"<div class='card'>{chart_bar(by_setup, 'setup', 'total_r', 'R total por setup')}{_table(by_setup)}</div>"
                     f"<div class='card'>{chart_bar(by_emotion, 'emotion_entry', 'total_r', 'R total por emocion al entrar')}{_table(by_emotion)}</div>"
                     "</div><div class='two'>"
                     f"<div class='card'><b>Seguiste el plan?</b>{_table(plan)}<br><b>Por fuente</b>{_table(by_source)}</div>"
                     f"<div class='card'><b>Costo de los errores</b>{_table(mistakes)}<br><b>Por activo</b>{_table(by_symbol)}</div>"
                     "</div>")
        if len(wd):
            parts.append(f"<div class='card'><b>Por dia de la semana (hora local)</b>{_table(wd.rename(columns={'size': 'trades', 'sum': 'total_r', 'mean': 'expectancy_r'}))}</div>")
    else:
        parts.append("<p class='muted'>Aun no hay operaciones cerradas. Registra operaciones con "
                     "<code>python main.py</code> (opcion Bitacora) o con la app <code>streamlit run app.py</code>.</p>")

    # Senales
    parts.append("<h2>Senales del sistema (resultado evaluado automaticamente)</h2>")
    parts.append("<div class='two'>"
                 f"<div class='card'><b>Por probabilidad</b>{_table(perf.signals_summary(signals))}</div>"
                 f"<div class='card'><b>Sistema vs tu ejecucion</b>{_table(perf.system_vs_you(trades, signals))}</div>"
                 "</div>")

    # Operaciones
    parts.append("<h2>Registro de operaciones</h2>")
    if len(trades):
        cols = ["id", "source", "symbol", "direction", "status", "entry_time", "entry_price",
                "stop_initial", "exit_time", "exit_price", "exit_reason", "r_multiple", "pnl",
                "setup", "confidence", "emotion_entry", "followed_plan", "features_status"]
        t = trades[cols].copy().iloc[::-1]
        t["id"] = t["id"].str[:8]
        parts.append(f"<div class='card'>{_table(t, 500)}</div>")
    else:
        parts.append("<p class='muted'>Sin operaciones.</p>")

    parts.append("<h2>Auditoria (ultimos eventos, cadena de hashes)</h2>")
    parts.append(f"<div class='card'>{_table(_events_table(journal))}</div>")

    parts.append("</div></body></html>")
    path.write_text("".join(parts), encoding="utf-8")
    return path
