def get_market_structure(df):

    highs = df[df["Swing_High"] == True]
    lows = df[df["Swing_Low"] == True]

    if len(highs) < 2 or len(lows) < 2:
        return "UNKNOWN"

    last_high = highs["High"].iloc[-1]
    prev_high = highs["High"].iloc[-2]

    last_low = lows["Low"].iloc[-1]
    prev_low = lows["Low"].iloc[-2]

    if last_high > prev_high and last_low > prev_low:
        return "UPTREND"

    if last_high < prev_high and last_low < prev_low:
        return "DOWNTREND"

    return "RANGE"