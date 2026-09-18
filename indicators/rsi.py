from ta.momentum import RSIIndicator

def calculate_rsi(df, period=14):

    close = df["Close"].squeeze()

    indicator = RSIIndicator(
        close=close,
        window=period
    )

    df["RSI"] = indicator.rsi()

    return df