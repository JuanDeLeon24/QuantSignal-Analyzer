def detect_bos(df):

    highs = df[df["Swing_High"] == True]

    lows = df[df["Swing_Low"] == True]

    if len(highs) < 2 or len(lows) < 2:
        return "NO BOS"

    last_close = df["Close"].iloc[-1]

    last_swing_high = highs["High"].iloc[-1]

    last_swing_low = lows["Low"].iloc[-1]

    if last_close > last_swing_high:
        return "BULLISH BOS"

    if last_close < last_swing_low:
        return "BEARISH BOS"

    return "NO BOS"