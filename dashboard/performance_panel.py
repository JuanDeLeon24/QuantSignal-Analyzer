import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt


def create_performance_panel(result):

    labels = [

        "Win Rate",
        "Profit Factor",
        "Drawdown"

    ]

    values = [

        result["win_rate"],
        result["profit_factor"] * 20,
        result["max_drawdown"]

    ]

    plt.figure(
        figsize=(8, 5)
    )

    plt.bar(
        labels,
        values,
        color=[
            "green",
            "blue",
            "orange"
        ]
    )

    plt.title(
        "Performance Panel"
    )

    plt.tight_layout()

    plt.savefig(
        "performance_panel.png"
    )

    plt.close()