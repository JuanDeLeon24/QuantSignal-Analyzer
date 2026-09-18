def get_trend(df):

    ema50 = df["EMA_50"].iloc[-1]
    ema200 = df["EMA_200"].iloc[-1]

    if ema50 > ema200:
        return "BULLISH"

    if ema50 < ema200:
        return "BEARISH"

    return "SIDEWAYS"