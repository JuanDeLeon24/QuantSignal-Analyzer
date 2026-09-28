"""Reporte HTML del estudio multi-activo (estrategias x universo)."""

from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from backtesting.engine import STRATEGIES
from config import settings
from reports import theme as T

DIV = LinearSegmentedColormap.from_list("div", [T.RED_S, "#f0efec", T.BLUE])


def chart_matrix(matrix):
    if matrix is None or matrix.empty:
        return ""
    m = matrix.copy()
    m.index = [STRATEGIES[k]["label"] for k in m.index]
    vals = m.values.astype(float)
    lim = max(0.2, np.nanpercentile(np.abs(vals), 95)) if np.isfinite(vals).any() else 1
    fig, ax = plt.subplots(figsize=(max(9, 0.28 * m.shape[1] + 3), 0.55 * m.shape[0] + 1.8))
    im = ax.imshow(np.ma.masked_invalid(vals), cmap=DIV, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    ax.set_xticks(range(m.shape[1]))
    ax.set_xticklabels(m.columns, rotation=70, ha="right", fontsize=7.5)
    ax.set_yticks(range(m.shape[0]))
    ax.set_yticklabels(m.index, fontsize=8.5)
    ax.grid(False)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Expectativa (R)")
    ax.set_title("Expectativa por estrategia y activo (gris = sin operaciones)")
    return T.img(fig, "Matriz estrategia x activo")


def chart_summary(summary):
    s = summary.dropna(subset=["expectancy_r"]).iloc[::-1]
    if not len(s):
        return ""
    fig, ax = plt.subplots(figsize=(6, 0.55 * len(s) + 1.2))
    y = np.arange(len(s))
    lo = s["expectancy_r"] - s["exp_ci_low"].fillna(s["expectancy_r"])
    hi = s["exp_ci_high"].fillna(s["expectancy_r"]) - s["expectancy_r"]
    cols = [T.BLUE if v > 0 else T.ORANGE for v in s["expectancy_r"]]
    ax.barh(y, s["expectancy_r"], color=cols, height=0.55)
    ax.errorbar(s["expectancy_r"], y, xerr=[lo, hi], fmt="none", ecolor=T.INK2, capsize=3, lw=1)
    ax.axvline(0, color=T.INK2, lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(s["estrategia"], fontsize=8.5)
    ax.set_xlabel("Expectativa por operacion (R) con IC95")
    ax.set_title("Todas las operaciones del universo")
    return T.img(fig, "Expectativa por estrategia")


def chart_class(by_class):
    if by_class is None or by_class.empty:
        return ""
    p = by_class.pivot(index="estrategia", columns="clase", values="expectancy_r")
    fig, ax = plt.subplots(figsize=(6, 0.55 * len(p) + 1.6))
    vals = p.values.astype(float)
    lim = max(0.2, np.nanmax(np.abs(vals))) if np.isfinite(vals).any() else 1
    im = ax.imshow(np.ma.masked_invalid(vals), cmap=DIV, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    ax.set_xticks(range(p.shape[1]))
    ax.set_xticklabels(p.columns, rotation=30, ha="right", fontsize=8.5)
    ax.set_yticks(range(p.shape[0]))
    ax.set_yticklabels(p.index, fontsize=8.5)
    ax.grid(False)
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            if np.isfinite(vals[i, j]):
                ax.text(j, i, f"{vals[i, j]:+.2f}", ha="center", va="center", fontsize=8, color=T.INK)
    ax.set_title("Expectativa (R) por clase de activo")
    return T.img(fig, "Por clase de activo")


def generate_study_report(st, path=None):
    settings.ensure_dirs()
    stamp = datetime.now()
    path = path or settings.REPORTS_DIR / f"estudio_universo_{stamp:%Y%m%d_%H%M}.html"
    s = st["summary"]
    tr = st["trades"]
    pct = lambda v: "–" if v is None or v != v else f"{v * 100:.1f}%"  # noqa: E731

    best = s.iloc[0] if len(s) else None
    kp = ""
    if best is not None:
        kp = ('<div class="grid">'
              + T.kpi("Activos estudiados", len(st["symbols"]), f"{len(st['errors'])} con error")
              + T.kpi("Operaciones simuladas", f"{len(tr):,}", f"{st['n_trials']} combinaciones probadas")
              + T.kpi("Mejor estrategia", T.esc(best["estrategia"]), T.esc(best["veredicto"]))
              + T.kpi("Expectativa", T.fmt(best["expectancy_r"], 3, sign=True) + " R",
                      f"IC95 {T.fmt(best['exp_ci_low'], 2, sign=True)} a {T.fmt(best['exp_ci_high'], 2, sign=True)}",
                      T.tone(best["expectancy_r"]))
              + T.kpi("Consistencia", T.fmt(best["consistencia_%"], 0) + "%", "activos con expectativa > 0")
              + T.kpi("Deflated Sharpe", pct(best["dsr"]), "corrige todas las pruebas")
              + "</div>")
    mc = st.get("best_mc")
    mc_txt = ""
    if mc:
        mc_txt = (f"<p class='note'>Monte Carlo de la mejor estrategia sobre las {mc['n_trades']:,} operaciones del universo "
                  f"(riesgo {mc['risk_pct']:.2f}% por operacion, porque se reparte entre muchos activos): retorno P5 "
                  f"{mc['final_return_pct'][5]:+.1f}%, P50 {mc['final_return_pct'][50]:+.1f}%, P95 {mc['final_return_pct'][95]:+.1f}% · "
                  f"drawdown P95 {mc['max_drawdown_pct'][95]:.1f}%.</p>")
    body = [
        "<header class='top'><div><div class='brand'>QuantSignal AI · Estudio multi-activo</div>"
        f"<h1>{len(STRATEGIES)} estrategias × {len(st['symbols'])} activos</h1>"
        f"<div class='meta'>Generado {stamp:%Y-%m-%d %H:%M} · intervalo {T.esc(settings.INTERVAL)} · historico "
        f"{T.esc(settings.PERIOD)} · costes {settings.FEE_PCT * 100:.2f}% + {settings.SLIPPAGE_PCT * 100:.2f}% por lado</div></div></header>",
        "<section><h2>Resumen</h2>" + kp + mc_txt
        + "<p class='note'>Una estrategia fiable debe tener expectativa positiva <b>en la mayoria de los activos</b> "
          "(consistencia) y un intervalo de confianza que no cruce el cero. Si solo funciona en 2 o 3 activos, "
          "probablemente sea casualidad.</p></section>",
        "<section><h2>Ranking de estrategias</h2><div class='two'>"
        f"<div class='card'>{chart_summary(s)}</div><div class='card'>{chart_class(st['by_class'])}</div></div>"
        "<div class='card' style='margin-top:14px'>"
        + T.table(s.drop(columns=["clave"]), formats={"veredicto": T.badge, "dsr": pct, "p_value": lambda v: T.fmt(v, 4),
                                                      "expectancy_r": lambda v: T.fmt(v, 3, sign=True)},
                  tones=["expectancy_r", "mediana_activo_r"]) + "</div></section>",
        f"<section><h2>Mapa estrategia × activo</h2><div class='card'>{chart_matrix(st['matrix'])}</div></section>",
    ]
    if st.get("by_year") is not None and len(st["by_year"]):
        body.append("<section><h2>Estabilidad por año</h2><div class='card'>"
                    + T.table(st["by_year"].rename_axis("estrategia"), index=True) + "</div></section>")
    if len(st["by_class"]):
        body.append("<section><h2>Detalle por clase de activo</h2><div class='card'>"
                    + T.table(st["by_class"], tones=["expectancy_r"], formats={"p_value": lambda v: T.fmt(v, 4)})
                    + "</div></section>")
    if best is not None:
        pa = st["per_asset"]
        top = pa[pa["estrategia"] == best["clave"]].sort_values("expectancy_r", ascending=False)
        body.append(f"<section><h2>{T.esc(best['estrategia'])}: resultado por activo</h2><div class='card'>"
                    + T.table(top.drop(columns=["estrategia"]), tones=["expectancy_r", "total_r"]) + "</div></section>")
    body.append("<section><h2>Referencia: comprar y mantener</h2><div class='card'>"
                + T.table(st["benchmark"], tones=["bh_cagr_%"]) + "</div></section>")
    if st.get("trades_path"):
        body.append(f"<p class='note'>Todas las operaciones simuladas estan en <code>{T.esc(st['trades_path'])}</code>.</p>")
    if st["errors"]:
        body.append("<p class='note'>Sin datos: " + ", ".join(T.esc(k) for k in st["errors"]) + "</p>")
    path.write_text(T.page("Estudio multi-activo · QuantSignal AI", "".join(body), f"motor {settings.ENGINE_VERSION}"),
                    encoding="utf-8")
    return path
