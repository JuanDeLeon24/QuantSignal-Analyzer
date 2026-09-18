def show_hh_hl(highs, lows):

    print("\n=========== HIGH STRUCTURE ===========")

    for item in highs[-5:]:

        print(
            f"{item['Date']} | {item['Type']} | {item['Value']:.2f}"
        )

    print("\n=========== LOW STRUCTURE ===========")

    for item in lows[-5:]:

        print(
            f"{item['Date']} | {item['Type']} | {item['Value']:.2f}"
        )