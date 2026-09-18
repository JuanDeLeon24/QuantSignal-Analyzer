def calculate_relative_volume(df):

    df["RVOL"] = (
        df["Volume"]
        / df["VOL_MA"]
    )

    return df
