def get_fibonacci_zone(price, levels):

    ordered = [
        levels["HIGH"],
        levels["0.236"],
        levels["0.382"],
        levels["0.500"],
        levels["0.618"],
        levels["0.786"],
        levels["LOW"]
    ]

    names = [
        "HIGH",
        "0.236",
        "0.382",
        "0.500",
        "0.618",
        "0.786",
        "LOW"
    ]

    for i in range(len(ordered) - 1):

        upper = ordered[i]
        lower = ordered[i + 1]

        if upper >= price >= lower:

            return f"{names[i]} -> {names[i+1]}"

    return "OUTSIDE RANGE"