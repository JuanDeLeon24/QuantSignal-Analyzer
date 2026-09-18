from ta.volatility import AverageTrueRange


def calculate_atr(df, period=14):

    atr = AverageTrueRange(
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        window=period
    )

    df["ATR"] = atr.average_true_range()

    return df