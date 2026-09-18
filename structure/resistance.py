def get_resistance(df):

    highs = df[df["Swing_High"] == True]

    if len(highs) == 0:
        return None

    return highs["High"].iloc[-1]