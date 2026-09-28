import pandas as pd


def normalize_ohlcv(df):
    """
    Deja el DataFrame con columnas: Date, Open, High, Low, Close, Volume.
    Date queda en UTC sin zona horaria para poder compararla siempre igual.
    """

    df = df.copy()

    # Elimina el segundo nivel del MultiIndex (yfinance >= 0.2.x)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    if "Date" not in df.columns:
        df = df.reset_index()

    # En intradia yfinance entrega "Datetime"
    for col in ["Datetime", "index", "timestamp"]:
        if col in df.columns and "Date" not in df.columns:
            df = df.rename(columns={col: "Date"})

    df["Date"] = pd.to_datetime(df["Date"], utc=True).dt.tz_localize(None)

    df = (
        df.dropna(subset=["Open", "High", "Low", "Close"])
        .sort_values("Date")
        .drop_duplicates(subset="Date")
        .reset_index(drop=True)
    )

    return df


_BAR = {
    "1m": pd.Timedelta(minutes=1), "5m": pd.Timedelta(minutes=5), "15m": pd.Timedelta(minutes=15),
    "30m": pd.Timedelta(minutes=30), "1h": pd.Timedelta(hours=1), "4h": pd.Timedelta(hours=4),
    "1d": pd.Timedelta(days=1), "1wk": pd.Timedelta(weeks=1),
}


def drop_incomplete(df, interval="1d", now=None):
    """
    Quita la ultima vela si todavia no ha cerrado (p. ej. la vela diaria de hoy).
    Analizar una vela en curso hace que las senales "cambien" durante el dia.
    Acciones/ETF (sin velas en fin de semana): la vela diaria cierra ~21:00 UTC.
    """
    if df is None or len(df) < 2:
        return df
    now = pd.Timestamp.now("UTC").tz_localize(None) if now is None else pd.Timestamp(now)
    last = pd.Timestamp(df["Date"].iloc[-1])
    bar = _BAR.get(interval, pd.Timedelta(days=1))
    if interval in ("1d", "1wk"):
        weekend = (pd.to_datetime(df["Date"]).dt.dayofweek >= 5).mean() > 0.1
        close_at = last + (bar if weekend else (bar - pd.Timedelta(days=1)) + pd.Timedelta(hours=21))
    else:
        close_at = last + bar
    if now < close_at:
        df = df.iloc[:-1].reset_index(drop=True)
        df.attrs["incomplete_dropped"] = str(last)
    return df


def load_data(symbol, period="5y", interval="1d", start=None, end=None, closed_only=None):

    import yfinance as yf

    kwargs = dict(
        interval=interval,
        auto_adjust=True,
        progress=False,
    )

    if start is not None:
        kwargs["start"] = start
        if end is not None:
            kwargs["end"] = end
    else:
        kwargs["period"] = period

    df = yf.download(symbol, **kwargs)

    if df is None or len(df) == 0:
        raise ValueError(
            f"No se pudieron descargar datos para {symbol} ({interval})"
        )

    df = normalize_ohlcv(df)

    if closed_only is None:
        from config import settings
        closed_only = settings.DROP_INCOMPLETE_CANDLE
    if closed_only and start is None:
        df = drop_incomplete(df, interval)

    return df
