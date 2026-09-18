def get_support(df):

    lows = df[df["Swing_Low"] == True]

    if len(lows) == 0:
        return None

    return lows["Low"].iloc[-1]