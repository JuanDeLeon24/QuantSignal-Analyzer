import pandas as pd


def detect_order_blocks(df):

    bullish_ob = None
    bearish_ob = None

    for i in range(5, len(df) - 1):

        current_close = df["Close"].iloc[i]
        previous_open = df["Open"].iloc[i - 1]
        previous_close = df["Close"].iloc[i - 1]

        # Bullish OB
        if (
            previous_close < previous_open
            and current_close > df["High"].iloc[i - 1]
        ):

            bullish_ob = {
                "type": "BULLISH",
                "high": float(df["High"].iloc[i - 1]),
                "low": float(df["Low"].iloc[i - 1]),
                "price": float(previous_close)
            }

        # Bearish OB
        if (
            previous_close > previous_open
            and current_close < df["Low"].iloc[i - 1]
        ):

            bearish_ob = {
                "type": "BEARISH",
                "high": float(df["High"].iloc[i - 1]),
                "low": float(df["Low"].iloc[i - 1]),
                "price": float(previous_close)
            }

    return {
        "bullish": bullish_ob,
        "bearish": bearish_ob
    }