def choch_bullish(df, index):

    if index < 5:
        return False

    current_low = df["Low"].iloc[index]

    previous_lows = df[
        "Low"
    ].iloc[index - 5:index]

    return (
        current_low >
        previous_lows.min()
    )