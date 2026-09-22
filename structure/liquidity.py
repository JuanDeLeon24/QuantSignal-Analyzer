def detect_liquidity(df):

    if len(df) < 10:
        return "NONE"

    recent_high = max(
        df["High"].tail(10)
    )

    recent_low = min(
        df["Low"].tail(10)
    )

    last_high = float(
        df["High"].iloc[-1]
    )

    last_low = float(
        df["Low"].iloc[-1]
    )

    last_close = float(
        df["Close"].iloc[-1]
    )

    # Sweep arriba

    if (
        last_high > recent_high
        and last_close < recent_high
    ):
        return "BEARISH_SWEEP"

    # Sweep abajo

    if (
        last_low < recent_low
        and last_close > recent_low
    ):
        return "BULLISH_SWEEP"

    return "NONE"