import numpy as np
import pandas as pd

from ml.features import add_indicators, feature_columns, feature_row, index_at_or_before
from ml.labeling import simulate_outcome


def test_no_lookahead(ohlcv):
    """Cambiar el futuro no debe cambiar las features del presente."""
    i = 600
    a = feature_row(add_indicators(ohlcv), i)
    future_changed = ohlcv.copy()
    future_changed.loc[i + 1:, ["Open", "High", "Low", "Close"]] *= 3
    b = feature_row(add_indicators(future_changed), i)
    assert a == b


def test_feature_schema_stable(ohlcv):
    f = feature_row(add_indicators(ohlcv), 500)
    assert list(f) == feature_columns()
    assert all(v is None or np.isfinite(v) for v in f.values())


def test_index_uses_closed_candle(ohlcv):
    # entrada el dia 10 a las 14:00 -> la vela del dia 10 no ha cerrado -> usa la del 9
    i = index_at_or_before(ohlcv, pd.Timestamp("2022-01-10 14:00"))
    assert ohlcv["Date"].iloc[i] == pd.Timestamp("2022-01-09")


def test_outcome_conservative():
    fut = pd.DataFrame({"Date": pd.date_range("2024-01-01", periods=3),
                        "High": [106, 112, 100], "Low": [99, 94, 90], "Close": [105, 100, 95]})
    r = simulate_outcome(fut, "LONG", 100, 95, 110, 20)
    assert r["outcome"] == "LOSS" and r["bars"] == 2        # misma vela SL y TP -> SL
    r = simulate_outcome(fut.iloc[:1], "LONG", 100, 95, 110, 20)
    assert r["outcome"] == "OPEN"
    r = simulate_outcome(fut, "SHORT", 100, 113, 90, 20)
    assert r["outcome"] == "WIN" and abs(r["r_result"] - 10 / 13) < 1e-3
