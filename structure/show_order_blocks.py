def show_order_blocks(ob):

    print(
        "\n=========== ORDER BLOCKS ==========="
    )

    if ob["bullish"]:

        print(
            "\nBullish OB"
        )

        print(
            "High:",
            round(
                ob["bullish"]["high"],
                2
            )
        )

        print(
            "Low:",
            round(
                ob["bullish"]["low"],
                2
            )
        )

    if ob["bearish"]:

        print(
            "\nBearish OB"
        )

        print(
            "High:",
            round(
                ob["bearish"]["high"],
                2
            )
        )

        print(
            "Low:",
            round(
                ob["bearish"]["low"],
                2
            )
        )