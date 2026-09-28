import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt


def create_equity_curve(equity_values, path="equity_curve.png", title="Equity Curve"):

    plt.figure(figsize=(10, 5))

    plt.plot(equity_values, color="#1a7f37", linewidth=2)

    plt.title(title)
    plt.xlabel("Trades")
    plt.ylabel("Capital")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=110)
    plt.close()

    return str(path)
