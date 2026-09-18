def show_fibonacci(levels):

    if levels is None:
        return

    print("\n=========== FIBONACCI ===========")

    for key, value in levels.items():

        print(
            f"{key:>6} : {value:.2f}"
        )