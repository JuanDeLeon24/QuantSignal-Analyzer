def calculate_volume_ma(df, period=20):

    df["VOL_MA"] = (
        df["Volume"]
        .rolling(period)
        .mean()
    )

    return df