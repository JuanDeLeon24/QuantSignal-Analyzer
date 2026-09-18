def show_confluence(score, factors):

    print(
        "\n=========== CONFLUENCIAS ==========="
    )

    for factor in factors:

        print(factor)

    print()

    print(
        f"Score: {score}/100"
    )

    if score >= 90:

        print(
            "Probabilidad: EXTREMA"
        )

    elif score >= 75:

        print(
            "Probabilidad: MUY ALTA"
        )

    elif score >= 60:

        print(
            "Probabilidad: ALTA"
        )

    elif score >= 40:

        print(
            "Probabilidad: MEDIA"
        )

    else:

        print(
            "Probabilidad: BAJA"
        )