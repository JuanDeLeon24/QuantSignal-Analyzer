def classify_structure(df):

    highs = df[df["Swing_High"] == True].copy()
    lows = df[df["Swing_Low"] == True].copy()

    high_results = []
    low_results = []

    # HIGHS
    for i in range(1, len(highs)):

        current = highs["High"].iloc[i]
        previous = highs["High"].iloc[i - 1]

        if current > previous:
            label = "HH"
        else:
            label = "LH"

        high_results.append({
            "Date": highs["Date"].iloc[i],
            "Type": label,
            "Value": current
        })

    # LOWS
    for i in range(1, len(lows)):

        current = lows["Low"].iloc[i]
        previous = lows["Low"].iloc[i - 1]

        if current > previous:
            label = "HL"
        else:
            label = "LL"

        low_results.append({
            "Date": lows["Date"].iloc[i],
            "Type": label,
            "Value": current
        })

    return high_results, low_results