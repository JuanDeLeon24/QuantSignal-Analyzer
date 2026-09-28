import numpy as np
import pandas as pd

from analytics import stats as S
from tests.conftest import make_ohlcv


def test_trade_stats_significance():
    rng = np.random.default_rng(0)
    edge = rng.choice([2.0, -1.0], size=1000, p=[0.45, 0.55])     # E[R] = +0.35
    s = S.trade_stats(edge, n_trials=10)
    assert s["expectancy_ci"][0] > 0 and s["p_value"] < 0.01
    assert s["verdict"].startswith("VENTAJA")
    noise = rng.choice([1.0, -1.0], size=300)                          # E[R] = 0
    s2 = S.trade_stats(noise)
    assert s2["p_value"] > 0.01 and not s2["verdict"] == "VENTAJA SIGNIFICATIVA"
    assert S.trade_stats([1, -1])["verdict"] == "MUESTRA INSUFICIENTE"


def test_wilson_and_kelly():
    lo, hi = S.wilson_ci(50, 100)
    assert 39 < lo < 41 and 59 < hi < 61
    assert abs(S.kelly_fraction(0.5, 2.0) - 0.25) < 1e-9


def test_deflated_sharpe_penalizes_trials():
    rng = np.random.default_rng(1)
    r = rng.normal(0.1, 1, 200)
    assert S.deflated_sharpe(r, 100) < S.probabilistic_sharpe(r)


def test_monte_carlo_monotonic_risk():
    r = np.r_[np.full(40, 2.0), np.full(60, -1.0)]
    t = S.risk_of_ruin_table(r, risks=(0.5, 5), n_sims=500)
    assert t["dd_mediano_%"].iloc[1] > t["dd_mediano_%"].iloc[0]
    mc = S.monte_carlo(r, 1.0, n_sims=500)
    assert mc["final_return_pct"][5] <= mc["final_return_pct"][50] <= mc["final_return_pct"][95]


def test_engine_costs_and_no_lookahead():
    from backtesting.engine import BacktestConfig, prepare, run_backtest, strat_donchian
    df = make_ohlcv(n=1200, seed=4)
    d = prepare(df)
    sig = strat_donchian(d)
    free = run_backtest(d, sig, BacktestConfig(fee_pct=0, slippage_pct=0))
    paid = run_backtest(d, sig, BacktestConfig(fee_pct=0.002, slippage_pct=0.001))
    assert len(free.trades) == len(paid.trades) > 5
    assert paid.trades["r"].sum() < free.trades["r"].sum()
    # entrada siempre en la vela SIGUIENTE a la senal
    assert (pd.to_datetime(free.trades["entry_time"]) > pd.to_datetime(free.trades["signal_time"])).all()
    # cambiar el futuro no cambia las senales pasadas
    df2 = df.copy()
    df2.loc[1000:, ["Open", "High", "Low", "Close"]] *= 1.5
    sig2 = strat_donchian(prepare(df2))
    assert (sig.iloc[:990].values == sig2.iloc[:990].values).all()


def test_full_research_and_scenarios():
    from analytics.scenarios import build_scenarios
    from backtesting.engine import full_research, prepare
    df = make_ohlcv(n=1300, seed=8)
    r = full_research(df, symbol="X", n_mc=300)
    assert len(r["table"]) == 6 and "monte_carlo" in r
    assert r["grid_pivot"].shape == (4, 4)
    sc = build_scenarios(prepare(df), n_paths=500)
    for d in ("LONG", "SHORT"):
        e = sc["directions"][d]
        ps = [t["p_final"] for t in e["targets"]]
        assert ps[0] >= ps[1] >= ps[2]                     # objetivo mas lejano = menos probable
        assert 0 <= e["score"] <= 100
    assert sc["best_direction"] in ("LONG", "SHORT")


def test_drop_incomplete_candle():
    from data.data_loader import drop_incomplete
    df = pd.DataFrame({"Date": pd.date_range("2026-09-20", periods=9, freq="D"),
                       "Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 1.0})
    out = drop_incomplete(df, "1d", now=pd.Timestamp("2026-09-28 15:00"))
    assert len(out) == 8                                   # la vela del 28 aun no cierra
    out = drop_incomplete(df, "1d", now=pd.Timestamp("2026-09-29 00:30"))
    assert len(out) == 9


def test_choch_differs_from_bos():
    from structure.bos import detect_bos
    from structure.choch import detect_choch
    # estructura alcista y cierre por encima del ultimo high: BOS si, CHOCH no
    df = pd.DataFrame({
        "High": [10, 12, 11, 14, 13, 16],
        "Low": [8, 9, 9.5, 10, 11, 12],
        "Close": [9, 11, 10, 13, 12, 17],
        "Swing_High": [False, True, False, True, False, False],
        "Swing_Low": [True, False, True, False, False, False],
    })
    assert detect_bos(df) == "BULLISH BOS"
    assert detect_choch(df) == "NO CHOCH"
