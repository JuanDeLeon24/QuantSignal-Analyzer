from ta.trend import ADXIndicator


def calculate_adx(df, period=14):

    adx = ADXIndicator(
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        window=period
    )

    df["ADX"] = adx.adx()

    return df
