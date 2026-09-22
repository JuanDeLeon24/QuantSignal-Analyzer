def show_fvg(fvg):

    print(
        "\n=========== FVG ==========="
    )

    if not fvg:

        print(
            "No FVG detectado"
        )

        return

    print(
        "Tipo:",
        fvg["type"]
    )

    print(
        "Top:",
        round(
            fvg["top"],
            2
        )
    )

    print(
        "Bottom:",
        round(
            fvg["bottom"],
            2
        )
    )