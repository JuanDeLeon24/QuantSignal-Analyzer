def detect_swings(df, window=3):

    df = df.copy()

    df["Swing_High"] = (
        df["High"] ==
        df["High"].rolling(
            window=window * 2 + 1,
            center=True
        ).max()
    )

    df["Swing_Low"] = (
        df["Low"] ==
        df["Low"].rolling(
            window=window * 2 + 1,
            center=True
        ).min()
    )

    return df