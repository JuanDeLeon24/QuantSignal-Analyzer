import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt


def create_drawdown_chart(drawdowns, path="drawdown_chart.png", title="Drawdown"):

    plt.figure(figsize=(10, 5))

    values = [-abs(d) for d in drawdowns]

    plt.fill_between(range(len(values)), values, 0, color="#cf222e", alpha=0.25)
    plt.plot(values, color="#cf222e", linewidth=1.5)

    plt.title(title)
    plt.xlabel("Trades")
    plt.ylabel("Drawdown %")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=110)
    plt.close()

    return str(path)
