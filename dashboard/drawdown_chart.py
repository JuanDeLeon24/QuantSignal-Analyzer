import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt


def create_drawdown_chart(drawdowns):

    plt.figure(
        figsize=(10, 5)
    )

    plt.plot(
        drawdowns,
        color="red",
        linewidth=2
    )

    plt.title(
        "Drawdown"
    )

    plt.xlabel(
        "Trades"
    )

    plt.ylabel(
        "Drawdown %"
    )

    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        "drawdown_chart.png"
    )

    plt.close()