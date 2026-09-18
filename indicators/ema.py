def calculate_ema(df, period):

    df[f"EMA_{period}"] = (
        df["Close"]
        .ewm(span=period, adjust=False)
        .mean()
    )

    return df