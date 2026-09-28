"""Prueba de punta a punta con datos sinteticos (sin internet)."""
import pandas as pd
import pytest

from tests.conftest import make_ohlcv


def test_full_pipeline(journal, loader, monkeypatch):
    from core.analyzer import run_analysis
    from journal.enrichment import enrich_pending, evaluate_signals
    from ml.dataset import build_dataset, save_dataset
    from ml.model import predict_trade, train_model
    from paper_trading.trade_monitor import update_paper_trades
    from paper_trading.trade_manager import open_virtual_trade
    from reports.html_report import generate_html_report
    from reports import performance as perf

    full = loader("BTC-USD")
    # 1) Analisis con datos "hasta hace 30 velas" -> senal
    past = full.iloc[:-30].reset_index(drop=True)
    a = run_analysis("BTC-USD", df=past)
    assert a["trade_plan"]["direction"] in ("LONG", "SHORT", "NONE")
    a["created_at"] = (past["Date"].iloc[-1] + pd.Timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%S")
    a["trade_plan"]["direction"] = "LONG"   # forzar para evaluar
    sid = journal.log_signal(a)
    assert len(a["features"]) > 20

    # 2) Paper trade vinculado
    plan = dict(a["trade_plan"])
    tid_paper = open_virtual_trade("BTC-USD", "LONG", plan, signal_id=sid, journal=journal)
    journal.conn.execute("UPDATE trades SET entry_time=? WHERE id=?", (a["created_at"], tid_paper))

    # 3) Operaciones manuales en el pasado
    rows = full.iloc[300:700:20]
    for k, (_, r) in enumerate(rows.iterrows()):
        d = "LONG" if k % 2 == 0 else "SHORT"
        e = float(r["Close"])
        stop = e * (0.97 if d == "LONG" else 1.03)
        when = r["Date"] + pd.Timedelta(days=1, hours=2)
        t = journal.open_trade("BTC-USD", d, e, stop, risk_amount=100, entry_time=when,
                               setup="Pullback a EMA" if k % 3 else "Ruptura (BOS)",
                               emotion_entry="FOMO" if k % 4 == 0 else "Calmado", confidence=3)
        ex = float(full.loc[full["Date"] > when].iloc[5]["Close"])
        journal.close_trade(t, ex, when + pd.Timedelta(days=5), "MANUAL",
                            followed_plan=k % 3 != 0, mistakes=["Entrada anticipada"] if k % 5 == 0 else [])

    # 4) Enriquecer y evaluar
    res = enrich_pending(journal, loader=loader)
    assert set(res.values()) == {"OK"}
    ev = evaluate_signals(journal, loader=loader)
    assert ev["evaluated"] + ev["open"] >= 1
    closed_n = update_paper_trades(journal, loader=loader, log=lambda *x: None)
    assert closed_n in (0, 1)

    tr = journal.list_trades(status="CLOSED", source="MANUAL")
    assert tr["mae_r"].notna().all() and tr["features"].notna().all()

    # 5) Dataset + modelo
    ds = build_dataset(journal, symbols=["BTC-USD", "ETH-USD"], market_data={
        "BTC-USD": full, "ETH-USD": make_ohlcv(seed=3)}, log=lambda *x: None)
    assert {"MARKET", "MANUAL"} <= set(ds["source"])
    assert ds.loc[ds["source"] == "MANUAL", "weight"].iloc[0] == 4.0
    path, meta = save_dataset(ds)
    assert path.exists() and meta["rows"] == len(ds)

    card = train_model(ds, min_samples=100)
    assert "test_all" in card["metrics"] and card["warnings"]  # pocas operaciones -> aviso
    assert "baseline_logistica" in card["metrics"] and card["reliability"]
    p = predict_trade(a["features"], "LONG")
    assert 0 <= p["p_win"] <= 1

    # 6) Reportes
    s = perf.summary(journal.list_trades())
    assert s["trades"] >= 20
    html = generate_html_report(journal)
    text = html.read_text(encoding="utf-8")
    assert "Integridad OK" in text and "data:image/png;base64" in text
    assert journal.verify_integrity()["ok"]
