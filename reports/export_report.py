from datetime import datetime


def export_report(
    symbol,
    signal,
    conf_score,
    trade_plan,
    backtest
):

    file_name = (
        f"report_{symbol}.txt"
    )

    with open(
        file_name,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            "MARKET ANALYZER REPORT\n"
        )

        file.write(
            "=" * 50
        )

        file.write(
            "\n\n"
        )

        file.write(
            f"Fecha: {datetime.now()}\n\n"
        )

        file.write(
            f"Activo: {symbol}\n"
        )

        file.write(
            f"Señal: {signal}\n"
        )

        file.write(
            f"Confluencia: {conf_score}/100\n\n"
        )

        file.write(
            "TRADE PLAN\n"
        )

        file.write(
            "----------\n"
        )

        file.write(
            f"Entrada: {trade_plan['entry']}\n"
        )

        file.write(
            f"Stop: {trade_plan['stop']}\n"
        )

        file.write(
            f"TP1: {trade_plan['tp1']}\n"
        )

        file.write(
            f"TP2: {trade_plan['tp2']}\n"
        )

        file.write(
            f"TP3: {trade_plan['tp3']}\n"
        )

        file.write(
            f"RR: {trade_plan['rr']}\n\n"
        )

        file.write(
            "BACKTEST V2\n"
        )

        file.write(
            "-----------\n"
        )

        file.write(
            f"Trades: {backtest['trades']}\n"
        )

        file.write(
            f"Win Rate: {backtest['win_rate']}\n"
        )

        file.write(
            f"Profit Factor: {backtest['profit_factor']}\n"
        )

        file.write(
            f"Expectancy: {backtest['expectancy']}\n"
        )

        file.write(
            f"Drawdown: {backtest['max_drawdown']}\n"
        )

        file.write(
            f"Retorno: {backtest['return_pct']}%\n"
        )

    print(
        f"\n✅ Reporte exportado: {file_name}"
    )