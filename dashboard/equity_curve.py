import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt


def create_equity_curve(equity_values):

    plt.figure(
        figsize=(10, 5)
    )

    plt.plot(
        equity_values,
        color="green",
        linewidth=2
    )

    plt.title(
        "Equity Curve"
    )

    plt.xlabel(
        "Trades"
    )

    plt.ylabel(
        "Capital"
    )

    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        "equity_curve.png"
    )

    plt.close()