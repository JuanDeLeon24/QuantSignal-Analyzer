def detect_fvg(df):

    if len(df) < 5:
        return None

    for i in range(
        len(df) - 3,
        1,
        -1
    ):

        high_1 = float(
            df["High"].iloc[i - 1]
        )

        low_3 = float(
            df["Low"].iloc[i + 1]
        )

        low_1 = float(
            df["Low"].iloc[i - 1]
        )

        high_3 = float(
            df["High"].iloc[i + 1]
        )

        # Bullish FVG

        if low_3 > high_1:

            return {
                "type": "BULLISH",
                "top": low_3,
                "bottom": high_1
            }

        # Bearish FVG

        if high_3 < low_1:

            return {
                "type": "BEARISH",
                "top": low_1,
                "bottom": high_3
            }

    return None