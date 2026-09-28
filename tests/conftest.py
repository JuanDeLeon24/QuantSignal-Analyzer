import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def make_ohlcv(n=900, seed=7, start="2022-01-01", freq="D", drift=0.0004, vol=0.02, price=100.0):
    rng = np.random.default_rng(seed)
    ret = rng.normal(drift, vol, n) + 0.01 * np.sin(np.arange(n) / 25)
    close = price * np.exp(np.cumsum(ret))
    open_ = np.r_[close[0], close[:-1]]
    spread = np.abs(rng.normal(0, vol * 0.6, n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    vol_ = rng.integers(1_000, 5_000, n).astype(float)
    return pd.DataFrame({
        "Date": pd.date_range(start, periods=n, freq=freq),
        "Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol_,
    })


@pytest.fixture
def ohlcv():
    return make_ohlcv()


@pytest.fixture
def journal(tmp_path, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(settings, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(settings, "DATASETS_DIR", tmp_path / "datasets")
    monkeypatch.setattr(settings, "CHARTS_DIR", tmp_path / "charts")
    monkeypatch.setattr(settings, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(settings, "STORAGE_DIR", tmp_path / "storage")
    monkeypatch.setattr(settings, "SCREENSHOTS_DIR", tmp_path / "storage" / "shots")
    from journal.repository import TradeJournal
    j = TradeJournal(tmp_path / "test.db")
    yield j
    j.close()


@pytest.fixture
def loader():
    """Loader falso: siempre devuelve el mismo historico sintetico."""
    data = {}

    def _load(symbol, period=None, interval="1d", start=None, end=None):
        if symbol not in data:
            data[symbol] = make_ohlcv(seed=abs(hash(symbol)) % 1000)
        df = data[symbol]
        if start is not None:
            df = df[df["Date"] >= pd.Timestamp(start)]
        if end is not None:
            df = df[df["Date"] < pd.Timestamp(end)]
        return df.reset_index(drop=True)

    _load.data = data
    return _load
