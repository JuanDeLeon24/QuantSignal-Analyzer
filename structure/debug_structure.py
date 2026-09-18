def show_structure(df):

    highs = df[df["Swing_High"] == True]

    lows = df[df["Swing_Low"] == True]

    print("\nULTIMOS SWING HIGHS")

    print(
        highs[
            ["Date", "High"]
        ].tail(5)
    )

    print("\nULTIMOS SWING LOWS")

    print(
        lows[
            ["Date", "Low"]
        ].tail(5)
    )