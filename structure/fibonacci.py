def calculate_fibonacci(df):

    highs = df[df["Swing_High"] == True]
    lows = df[df["Swing_Low"] == True]

    if len(highs) == 0 or len(lows) == 0:
        return None

    # Último impulso relevante
    high = highs["High"].iloc[-2]
    low = lows["Low"].iloc[-1]

    diff = high - low

    levels = {
        "HIGH": high,
        "0.236": high - diff * 0.236,
        "0.382": high - diff * 0.382,
        "0.500": high - diff * 0.500,
        "0.618": high - diff * 0.618,
        "0.786": high - diff * 0.786,
        "LOW": low
    }

    return levels