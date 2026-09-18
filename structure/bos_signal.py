def bos_bullish(df, index):

    if index < 5:
        return False

    current_high = df["High"].iloc[index]

    previous_highs = df[
        "High"
    ].iloc[index - 5:index]

    return (
        current_high >
        previous_highs.max()
    )