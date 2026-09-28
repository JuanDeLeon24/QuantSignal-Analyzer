import pandas as pd

from tests.conftest import make_ohlcv


def _loader(symbol, period=None, interval="1d", start=None, end=None, **kw):
    crypto = symbol.endswith("-USD")
    return make_ohlcv(n=1100 if crypto else 800, seed=sum(map(ord, symbol)) % 997,
                      freq="D" if crypto else "B", vol=0.03 if crypto else 0.012)


def test_universe_has_50_unique_assets():
    from config import settings
    assert len(settings.WATCHLIST) == 50 == len(set(settings.WATCHLIST))
    assert all(settings.asset_class(s) != "Otros" for s in settings.WATCHLIST)


def test_cache_roundtrip(tmp_path, monkeypatch):
    from config import settings
    from data import cache
    monkeypatch.setattr(settings, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(settings, "DROP_INCOMPLETE_CANDLE", False)
    calls = []

    def loader(*a, **k):
        calls.append(a)
        return _loader(*a)

    df1 = cache.get_data("GC=F", "5y", "1d", loader=loader)
    df2 = cache.get_data("GC=F", "5y", "1d", loader=loader)      # desde cache
    assert len(calls) == 1 and len(df1) == len(df2)
    assert cache.cache_path("GC=F", "1d", "5y").exists()
    assert pd.api.types.is_datetime64_any_dtype(df2["Date"])


def test_cross_asset_analogs():
    from analytics.scenarios import build_scenarios
    from backtesting.engine import prepare
    pool = {s: prepare(_loader(s)) for s in ("ETH-USD", "SPY", "GC=F", "EURUSD=X")}
    sc = build_scenarios(pool["ETH-USD"], pool=pool, symbol="ETH-USD", k=80, n_paths=400)
    assert sc["scope"] == "universo" and sc["pool_size"] == 4
    assert sc["n_assets"] >= 2
    assert sc["n_effective"] <= sc["n_analogs"]
    assert "activo" in sc["analog_table"].columns
    # cada activo aporta como maximo max(10, k//4) = 20 casos
    assert sc["analog_assets"]["analogos"].max() <= 20


def test_universe_study_and_scanner(tmp_path, monkeypatch):
    from config import settings
    for k in ("REPORTS_DIR", "DATASETS_DIR", "OUTPUT_DIR"):
        monkeypatch.setattr(settings, k, tmp_path / k)
    from analytics.universe_study import universe_study
    from reports.study_report import generate_study_report
    syms = ["BTC-USD", "SPY", "GC=F", "EURUSD=X"]
    st = universe_study(symbols=syms, loader=_loader, save=True)
    assert len(st["summary"]) == 6 and st["n_trials"] == 24
    assert set(st["trades"]["clase"]) <= {"Cripto", "Indices y ETF", "Materias primas", "Forex"}
    assert st["trades_path"].exists()
    assert "Estudio multi-activo" in generate_study_report(st).read_text(encoding="utf-8")

    from analytics.scanner import scan
    from reports.scanner_report import generate_scanner_report
    res = scan(symbols=syms, loader=_loader, with_backtest=False, log=lambda *x: None)
    assert len(res["table"]) == 4 and len(res["by_class"]) == 4
    assert res["analyses"]["SPY"]["scenarios"]["pool_size"] == 4
    assert generate_scanner_report(res).exists()
