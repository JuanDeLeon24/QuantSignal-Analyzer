import matplotlib
matplotlib.use("Agg")

from config.settings import CHARTS_DIR, ensure_dirs

from dashboard.equity_curve import create_equity_curve
from dashboard.drawdown_chart import create_drawdown_chart
from dashboard.performance_panel import create_performance_panel


def generate_dashboard(result, symbol="backtest"):
    """
    Genera graficas del backtest usando la curva de equity REAL
    (antes se dibujaba una linea recta interpolada).
    """

    ensure_dirs()

    safe = str(symbol).replace("/", "_")

    equity_values = result.get("equity_curve") or [result.get("equity", 0)]
    drawdowns = result.get("drawdown_curve") or [0]

    paths = [
        create_equity_curve(
            equity_values, CHARTS_DIR / f"equity_curve_{safe}.png",
            title=f"Equity Curve - {symbol}"
        ),
        create_drawdown_chart(
            drawdowns, CHARTS_DIR / f"drawdown_{safe}.png",
            title=f"Drawdown - {symbol}"
        ),
        create_performance_panel(
            result, CHARTS_DIR / f"performance_{safe}.png"
        ),
    ]

    print("\n✅ Dashboard generado")

    for p in paths:
        print("  ", p)

    return paths
