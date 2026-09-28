"""Reporte HTML del escaner de oportunidades (ranking + comparacion de activos)."""

from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from config import settings
from reports import theme as T


def chart_scores(table, top=20):
    t = table.sort_values("score", ascending=False).head(top).sort_values("score")
    fig, ax = plt.subplots(figsize=(6, max(2.4, 0.5 * len(t) + 1)))
    y = np.arange(len(t))
    ax.barh(y - 0.2, t["conf_long"], 0.36, color=T.BLUE, label="Confluencia LONG")
    ax.barh(y + 0.2, t["conf_short"], 0.36, color=T.ORANGE, label="Confluencia SHORT")
    ax.scatter(t["score"], y, color=T.INK, zorder=3, s=30, label="Decision Score")
    ax.set_yticks(y)
    ax.set_yticklabels(t["activo"])
    ax.set_xlim(0, 100)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3)
    ax.set_title(f"Puntuacion: {len(t)} mejores activos")
    return T.img(fig, "Puntuaciones")


def chart_relative(prices, symbols=None):
    if prices is None or prices.empty:
        return ""
    if symbols:
        prices = prices[[s for s in symbols if s in prices.columns][:8]]
    base = prices.bfill().iloc[0]
    norm = prices / base * 100
    fig, ax = plt.subplots(figsize=(6, 3.6))
    for k, col in enumerate(norm.columns[:8]):
        ax.plot(norm.index, norm[col], color=T.SERIES[k % 8], lw=1.6, label=col)
        ax.text(norm.index[-1], norm[col].iloc[-1], f" {col}", fontsize=8, color=T.INK2, va="center")
    ax.axhline(100, color=T.INK2, lw=0.8)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=4)
    ax.set_title("Rendimiento relativo de los 8 mejores (base 100)")
    fig.autofmt_xdate()
    return T.img(fig, "Rendimiento relativo")


def top_pairs(corr, n=15):
    if corr is None or corr.empty:
        return pd.DataFrame()
    c = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1)).stack()
    c = c.reindex(c.abs().sort_values(ascending=False).index).head(n)
    return pd.DataFrame({"activo_a": [a for a, _ in c.index], "activo_b": [b for _, b in c.index],
                         "correlacion": c.values.round(3)})


def chart_corr(corr, symbols=None):
    if corr is None or corr.empty:
        return ""
    if symbols:
        keep = [s for s in symbols if s in corr.columns][:10]
        corr = corr.loc[keep, keep]
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    cmap = LinearSegmentedColormap.from_list("div", [T.RED_S, "#f0efec", T.BLUE])
    im = ax.imshow(corr.values, cmap=cmap, norm=TwoSlopeNorm(0, -1, 1))
    ax.set_xticks(range(len(corr)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr)))
    ax.set_yticklabels(corr.index)
    ax.grid(False)
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=7, color=T.INK)
    fig.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title(f"Correlacion de retornos diarios ({len(corr)} mejores)")
    return T.img(fig, "Correlaciones")


def generate_scanner_report(result, path=None):
    settings.ensure_dirs()
    stamp = datetime.now()
    path = path or settings.REPORTS_DIR / f"escaner_{stamp:%Y%m%d_%H%M}.html"
    t = result["table"]
    comp = result.get("comparison") or {}
    pct = lambda v: "–" if v is None or v != v else f"{v * 100:.1f}%"  # noqa: E731

    top = t.iloc[0] if len(t) else None
    hero = ""
    if top is not None:
        hero = ('<div class="grid">'
                + T.kpi("Mejor oportunidad", T.esc(top["activo"]), T.esc(top["accion"]))
                + T.kpi("Decision Score", T.fmt(top["score"], 0), T.esc(top["veredicto"]))
                + T.kpi("P(TP2)", pct(top["p_tp2"]), f'ventaja {T.fmt(top["ventaja_pp"], 1, sign=True)} pp')
                + T.kpi("Valor esperado", T.fmt(top["ev_neto_r"], 2, sign=True) + " R", "neto de costes", T.tone(top["ev_neto_r"]))
                + T.kpi("Favorables", int((t["veredicto"] == "FAVORABLE").sum()), f"de {len(t)} activos")
                + "</div>")

    cols = ["rank", "activo", "nombre", "clase", "precio", "accion", "score", "veredicto", "p_tp2", "ventaja_pp", "ev_neto_r",
            "riesgo_%", "senal_tecnica", "ret_20v_%", "atr_%", "mejor_estrategia", "exp_estrategia_r", "veredicto_backtest"]
    cols = [c for c in cols if c in t.columns]
    body = [
        "<header class='top'><div><div class='brand'>QuantSignal AI · Escaner de oportunidades</div>"
        f"<h1>Watchlist ({len(t)} activos)</h1><div class='meta'>Generado {stamp:%Y-%m-%d %H:%M} · "
        f"intervalo {T.esc(settings.INTERVAL)} · riesgo base {settings.RISK_PERCENT}% · capital ${settings.ACCOUNT_SIZE:,.0f}</div></div></header>",
        "<section><h2>Resumen</h2>" + hero + "</section>",
        "<section><h2>Ranking</h2><div class='card'>"
        + T.table(t[cols], formats={"p_tp2": pct, "veredicto": T.badge, "veredicto_backtest": T.badge,
                                    "precio": lambda v: T.fmt(v, 4), "ventaja_pp": lambda v: T.fmt(v, 1, sign=True),
                                    "ev_neto_r": lambda v: T.fmt(v, 3, sign=True)},
                  tones=["ev_neto_r", "ventaja_pp", "ret_20v_%", "exp_estrategia_r"])
        + "</div></section>",
        "<section><h2>Por clase de activo</h2><div class='card'>"
        + T.table(result.get("by_class"), tones=["ev_medio_r"]) + "</div></section>",
        f"<section><h2>Comparacion entre activos</h2><div class='two'><div class='card'>{chart_scores(t)}</div>"
        f"<div class='card'>{chart_relative(comp.get('prices'), list(t['activo']) if len(t) else None)}</div></div>",
        "<div class='two' style='margin-top:14px'>"
        f"<div class='card'>{chart_corr(comp.get('corr'), list(t['activo']) if len(t) else None)}</div>"
        f"<div class='card'><h3>Pares mas correlacionados del universo</h3>{T.table(top_pairs(comp.get('corr')), tones=['correlacion'])}"
        "<p class='note'>Activos muy correlacionados (&gt;0.7) suman el mismo riesgo: operar varios a la vez "
        "equivale a una posicion mas grande.</p></div></div>"
        f"<div class='card' style='margin-top:14px'><h3>Fuerza relativa y riesgo (todos)</h3>"
        f"{T.table(comp.get('stats'), tones=['ret_20_%', 'ret_60_%', 'ret_periodo_%', 'sharpe_periodo'])}</div></section>",
    ]
    if result.get("errors"):
        body.append("<p class='note'>No se pudieron analizar: "
                    + ", ".join(f"{T.esc(k)} ({T.esc(v)[:80]})" for k, v in result["errors"].items()) + "</p>")
    path.write_text(T.page("Escaner · QuantSignal AI", "".join(body), f"motor {settings.ENGINE_VERSION}"), encoding="utf-8")
    return path
