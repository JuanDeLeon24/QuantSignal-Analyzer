def calculate_score(df):

    score = 0

    ema50 = df["EMA_50"].iloc[-1]
    ema200 = df["EMA_200"].iloc[-1]

    rsi = df["RSI"].iloc[-1]

    macd = df["MACD"].iloc[-1]
    macd_signal = df["MACD_SIGNAL"].iloc[-1]

    adx = df["ADX"].iloc[-1]

    # Tendencia
    if ema50 > ema200:
        score += 30

    # RSI
    if rsi > 50:
        score += 20

    # MACD
    if macd > macd_signal:
        score += 25

    # ADX
    if adx > 25:
        score += 25

    return score