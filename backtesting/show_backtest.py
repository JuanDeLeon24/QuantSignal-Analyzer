def show_backtest(result):

    print("\n=========== BACKTEST ===========")

    print("Trades        :", result["trades"])

    print("Ganadores     :", result["wins"])

    print("Perdedores    :", result["losses"])

    print("Win Rate %    :", result["win_rate"])

    print("Profit Factor :", result["profit_factor"])

    print("Gross Profit  :", result["gross_profit"])

    print("Gross Loss    :", result["gross_loss"])

    print("Expectancy    :", result["expectancy"])

    print("Equity Final  :", result["final_equity"])

    print("Retorno %     :", result["return_pct"])

    print("Max Drawdown  :", result["max_drawdown"])

    if result["profit_factor"] >= 2:

        print("Calidad       : EXCELENTE")

    elif result["profit_factor"] >= 1.5:

        print("Calidad       : BUENA")

    elif result["profit_factor"] >= 1:

        print("Calidad       : ACEPTABLE")

    else:

        print("Calidad       : DEFICIENTE")