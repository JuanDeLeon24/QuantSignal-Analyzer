import matplotlib
matplotlib.use("Agg")

from dashboard.equity_curve import (
    create_equity_curve
)

from dashboard.drawdown_chart import (
    create_drawdown_chart
)

from dashboard.performance_panel import (
    create_performance_panel
)


def generate_dashboard(
    result
):

    trades = result["trades"]

    equity_values = []

    capital = 10000

    step = (
        result["equity"] - 10000
    ) / max(1, trades)

    for _ in range(trades):

        capital += step

        equity_values.append(
            capital
        )

    drawdowns = [

        result["max_drawdown"]
    ] * max(1, trades)

    create_equity_curve(
        equity_values
    )

    create_drawdown_chart(
        drawdowns
    )

    create_performance_panel(
        result
    )

    print(
        "\n✅ Dashboard generado"
    )

    print(
        "equity_curve.png"
    )

    print(
        "drawdown_chart.png"
    )

    print(
        "performance_panel.png"
    )