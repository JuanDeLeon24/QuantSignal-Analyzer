"""
Estilo comun de los reportes HTML y graficas (paleta validada para
daltonismo, tipografia del sistema, tablas y tarjetas).
"""

import base64
import html
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

# Paleta categorica (orden fijo) y colores de estado
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN_S, VIOLET, RED_S = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
SERIES = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN_S, VIOLET, RED_S]
GOOD, WARN, SERIOUS, CRIT = "#0ca30c", "#fab219", "#ec835a", "#d03b3b"
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"

plt.rcParams.update({
    "font.family": ["DejaVu Sans"],
    "font.size": 9.5,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": INK2,
    "axes.titlecolor": INK,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "legend.frameon": False,
    "legend.fontsize": 8.5,
    "lines.linewidth": 2,
})


def img(fig, alt="grafica"):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return (f'<img class="chart" alt="{html.escape(alt)}" '
            f'src="data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}">')


def esc(x):
    return html.escape(str(x))


def fmt(v, dec=2, pct=False, sign=False):
    if v is None:
        return "–"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return esc(v)
    if f != f:
        return "–"
    s = f"{f:+,.{dec}f}" if sign else f"{f:,.{dec}f}"
    return s + ("%" if pct else "")


def tone(v, good=0.0):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ""
    return "pos" if f > good else "neg" if f < good else ""


HEADERS = {
    "expectancy_r": "Expectativa (R)", "win_rate": "Win %", "profit_factor": "Profit factor",
    "total_r": "R total", "total_pnl": "PnL $", "trades": "Trades", "p_value": "p-valor",
    "psr": "PSR", "dsr": "DSR", "cagr_pct": "CAGR %", "sharpe": "Sharpe", "max_dd_pct": "Max DD %",
    "exposicion_pct": "Exposicion %", "sqn": "SQN", "estrategia": "Estrategia", "veredicto": "Veredicto",
    "regime_trend": "Tendencia", "regime_vol": "Volatilidad", "direction": "Direccion", "reason": "Salida",
    "segmento": "Segmento", "desde": "Desde", "hasta": "Hasta", "IC95_expectativa": "IC95 expectativa",
    "entry_time": "Entrada", "exit_time": "Salida", "entry": "Precio entrada", "exit": "Precio salida",
    "bars": "Velas", "r": "R neto", "mae_r": "MAE (R)", "mfe_r": "MFE (R)",
    "exp_ci_low": "IC95 bajo", "exp_ci_high": "IC95 alto", "activos_con_ops": "Activos",
    "consistencia_%": "Consistencia %", "mediana_activo_r": "Mediana por activo (R)",
    "clase": "Clase", "activo": "Activo", "index": "", "casos_indep": "Casos indep.",
}


def _hdr(c):
    return HEADERS.get(c, str(c).replace("_", " "))


def table(df, max_rows=200, formats=None, tones=None, index=False):
    """Tabla HTML con formato por columna y color de signo opcional."""
    if df is None or len(df) == 0:
        return '<p class="muted">Sin datos.</p>'
    formats = formats or {}
    tones = set(tones or [])
    d = df.head(max_rows)
    if index:
        d = d.reset_index()
    head = "".join(f"<th>{esc(_hdr(c))}</th>" for c in d.columns)
    rows = []
    for _, r in d.iterrows():
        tds = []
        for c in d.columns:
            v = r[c]
            if c in formats:
                s = formats[c](v)
            elif isinstance(v, float):
                s = fmt(v, 3 if abs(v) < 10 else 2)
            elif isinstance(v, tuple):
                s = " – ".join(fmt(x, 3) for x in v)
            else:
                s = "–" if v is None or (isinstance(v, float) and v != v) else esc(v)
            cls = tone(v) if c in tones else ""
            num = isinstance(v, (int, float)) and not isinstance(v, bool)
            tds.append(f'<td class="{cls}{" num" if num else ""}">{s}</td>')
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return f'<div class="tbl-wrap"><table class="tbl"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def kpi(label, value, sub="", cls=""):
    return (f'<div class="kpi {cls}"><div class="l">{esc(label)}</div>'
            f'<div class="v">{value}</div><div class="s">{sub}</div></div>')


def badge(text):
    t = str(text).upper()
    if ("FAVORABLE" in t and "DES" not in t) or "SIGNIFICATIVA" in t or t.startswith("LONG") or "INTEGR" in t:
        c = "good"
    elif "DESFAVORABLE" in t or "SIN VENTAJA" in t or t.startswith("SHORT") or "ALERTA" in t:
        c = "bad"
    elif any(k in t for k in ("MARGINAL", "PROBABLE", "DEBIL", "REDUCIDO", "CONFLICTO", "INSUFICIENTE")):
        c = "warn"
    else:
        c = "neutral"
    return f'<span class="badge {c}">{esc(text)}</span>'


def gauge(score, label="Decision Score"):
    s = 0 if score is None else max(0, min(100, float(score)))
    c = GOOD if s >= 65 else WARN if s >= 45 else CRIT
    return (f'<div class="gauge"><div class="gl">{esc(label)}</div>'
            f'<div class="gv">{s:.0f}<span>/100</span></div>'
            f'<div class="gt"><div class="gf" style="width:{s}%;background:{c}"></div></div></div>')


CSS = """
:root{--page:#f9f9f7;--card:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--line:#e1e0d9;
--ring:rgba(11,11,11,.10);--pos:#006300;--neg:#c02d2d;--accent:#2a78d6;--good:#0ca30c;--warn:#b57d00;--bad:#d03b3b}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--page:#0d0d0d;--card:#1a1a19;--ink:#fff;--ink2:#c3c2b7;
--muted:#898781;--line:#2c2c2a;--ring:rgba(255,255,255,.10);--pos:#0ca30c;--neg:#e66767;--accent:#3987e5;--warn:#fab219}}
:root[data-theme="dark"]{--page:#0d0d0d;--card:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;--line:#2c2c2a;
--ring:rgba(255,255,255,.10);--pos:#0ca30c;--neg:#e66767;--accent:#3987e5;--warn:#fab219}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--page);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 16px 64px}
header.top{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;justify-content:space-between;
border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:20px}
.brand{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
h1{font-size:26px;margin:2px 0 0;line-height:1.2}h2{font-size:17px;margin:34px 0 12px}
h3{font-size:14px;margin:0 0 8px}
.meta{color:var(--ink2);font-size:13px}.muted{color:var(--muted)}
nav.toc{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 8px}
nav.toc a{font-size:12.5px;color:var(--ink2);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:3px 10px}
nav.toc a:hover{color:var(--accent);border-color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,460px),1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--ring);border-radius:10px;padding:16px;min-width:0}
.kpi{background:var(--card);border:1px solid var(--ring);border-radius:10px;padding:12px 14px}
.kpi .l{color:var(--muted);font-size:12px}.kpi .v{font-size:22px;font-weight:650;margin-top:2px}
.kpi .s{color:var(--ink2);font-size:12px;min-height:1em}
.kpi.pos .v{color:var(--pos)}.kpi.neg .v{color:var(--neg)}
.hero{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:14px}
@media (max-width:760px){.hero{grid-template-columns:1fr}}
.verdict{font-size:30px;font-weight:700;margin:6px 0}
.badge{display:inline-block;font-size:12px;font-weight:650;padding:3px 10px;border-radius:999px;border:1px solid}
.badge.good{color:var(--pos);border-color:var(--pos)}.badge.bad{color:var(--neg);border-color:var(--neg)}
.badge.warn{color:var(--warn);border-color:var(--warn)}.badge.neutral{color:var(--ink2);border-color:var(--line)}
.gauge .gl{font-size:12px;color:var(--muted)}.gauge .gv{font-size:40px;font-weight:700;line-height:1.1}
.gauge .gv span{font-size:15px;color:var(--muted);font-weight:500}
.gt{height:8px;border-radius:4px;background:var(--line);overflow:hidden;margin-top:6px}.gf{height:100%;border-radius:4px}
ul.reasons{margin:8px 0 0;padding-left:18px}ul.checks{list-style:none;padding-left:0}ul.checks li{margin:5px 0}
.stack{display:grid;gap:14px}ul.reasons li{margin:4px 0;color:var(--ink2)}
.tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
.tbl{border-collapse:collapse;width:100%;font-size:12.5px}
.tbl th,.tbl td{padding:6px 9px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
.tbl th{color:var(--muted);font-weight:600;position:sticky;top:0;background:var(--card)}
.tbl td.num{text-align:right;font-variant-numeric:tabular-nums}
.tbl td.pos{color:var(--pos)}.tbl td.neg{color:var(--neg)}
img.chart{display:block;width:100%;height:auto;border-radius:6px;background:#fcfcfb}
.note{font-size:12.5px;color:var(--ink2);border-left:3px solid var(--line);padding:6px 12px;margin:10px 0}
details{margin-top:8px}summary{cursor:pointer;color:var(--ink2)}
footer{margin-top:40px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
@media print{nav.toc{display:none}.card,.kpi{break-inside:avoid}}
"""


def page(title, body, subtitle=""):
    return (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)}</title><style>{CSS}</style></head><body><div class='wrap'>"
        f"{body}<footer>QuantSignal AI · {esc(subtitle)} · Este reporte es analisis cuantitativo, "
        "no asesoria financiera. Resultados pasados no garantizan resultados futuros.</footer>"
        "</div></body></html>"
    )


def fmt_date(x):
    try:
        return pd.Timestamp(x).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return esc(x)
