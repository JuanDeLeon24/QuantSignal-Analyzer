def detect_choch(df):

    highs = df[df["Swing_High"] == True]

    lows = df[df["Swing_Low"] == True]

    if len(highs) < 2 or len(lows) < 2:
        return "NO CHOCH"

    last_close = df["Close"].iloc[-1]

    last_high = highs["High"].iloc[-1]

    last_low = lows["Low"].iloc[-1]

    if last_close > last_high:
        return "BULLISH CHOCH"

    if last_close < last_low:
        return "BEARISH CHOCH"

    return "NO CHOCH"