import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt


def create_performance_panel(result, path="performance_panel.png"):

    fig, axes = plt.subplots(1, 4, figsize=(12, 3))

    items = [
        ("Win Rate %", result.get("win_rate", 0), "#0969da"),
        ("Profit Factor", result.get("profit_factor", 0), "#1a7f37"),
        ("Expectancy (R)", result.get("expectancy_r", 0), "#8250df"),
        ("Max DD %", result.get("max_drawdown", 0), "#cf222e"),
    ]

    for ax, (label, value, color) in zip(axes, items):
        ax.axis("off")
        ax.text(0.5, 0.62, f"{value:,.2f}", ha="center", va="center",
                fontsize=24, color=color, weight="bold")
        ax.text(0.5, 0.25, label, ha="center", va="center", fontsize=11, color="#57606a")

    fig.suptitle(f"Backtest V2 - {result.get('trades', 0)} trades", fontsize=12)
    plt.tight_layout()
    plt.savefig(path, dpi=110)
    plt.close()

    return str(path)
