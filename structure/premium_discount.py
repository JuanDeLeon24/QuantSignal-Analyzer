def get_pd_zone(df):

    swing_high = float(
        df["High"].tail(50).max()
    )

    swing_low = float(
        df["Low"].tail(50).min()
    )

    midpoint = (
        swing_high + swing_low
    ) / 2

    current_price = float(
        df["Close"].iloc[-1]
    )

    if current_price > midpoint:
        return "PREMIUM"

    return "DISCOUNT"