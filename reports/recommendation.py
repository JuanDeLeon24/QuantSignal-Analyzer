def show_recommendation(
    symbol,
    signal,
    probability,
    trade_plan,
    backtest
):

    print(
        "\n=========== RECOMENDACION FINAL ==========="
    )

    print(
        "Activo       :",
        symbol
    )

    print(
        "Probabilidad :",
        probability
    )

    print(
        "Señal        :",
        signal
    )

    print()

    print(
        "Entrada      :",
        round(
            trade_plan["entry"],
            2
        )
    )

    print(
        "Stop Loss    :",
        round(
            trade_plan["stop"],
            2
        )
    )

    print(
        "TP1          :",
        round(
            trade_plan["tp1"],
            2
        )
    )

    print(
        "TP2          :",
        round(
            trade_plan["tp2"],
            2
        )
    )

    print(
        "TP3          :",
        round(
            trade_plan["tp3"],
            2
        )
    )

    print(
        "RR           :",
        round(
            trade_plan["rr"],
            2
        )
    )

    print()

    print(
        "============ BACKTEST V2 ============"
    )

    print(
        "Trades       :",
        backtest["trades"]
    )

    print(
        "Win Rate     :",
        backtest["win_rate"]
    )

    print(
        "ProfitFactor :",
        backtest["profit_factor"]
    )

    print(
        "Drawdown     :",
        backtest["max_drawdown"]
    )

    print()

    if (
        backtest["profit_factor"] >= 2
        and backtest["max_drawdown"] <= 30
    ):

        print(
            "✅ TOMAR OPERACION"
        )

    elif (

        backtest["profit_factor"] >= 1.5

    ):

        print(
            "⚠ OPERACION INTERESANTE - REVISAR"
        )

    else:

        print(
            "❌ EVITAR OPERACION"
        )