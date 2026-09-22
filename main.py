
from config.settings import *

from data.data_loader import load_data

from indicators.ema import calculate_ema
from indicators.rsi import calculate_rsi
from indicators.macd import calculate_macd
from indicators.atr import calculate_atr
from indicators.adx import calculate_adx

from indicators.volume import calculate_volume_ma
from indicators.relative_volume import calculate_relative_volume
from indicators.volume_signal import get_volume_signal

from strategy.trend import get_trend
from strategy.score import calculate_score
from strategy.signal import get_signal

from strategy.confluence import analyze_confluence
from strategy.show_confluence import show_confluence

from strategy.risk_manager import calculate_trade_plan
from strategy.position_size import calculate_position_size

from structure.swings import detect_swings
from structure.market_structure import get_market_structure
from structure.debug_structure import show_structure

from structure.hh_hl import classify_structure
from structure.show_hh_hl import show_hh_hl

from structure.bos import detect_bos
from structure.choch import detect_choch

from structure.support import get_support
from structure.resistance import get_resistance

from structure.fibonacci import calculate_fibonacci
from structure.show_fibonacci import show_fibonacci
from structure.fibonacci_zone import get_fibonacci_zone

from backtesting.simple_backtest import simple_backtest
from backtesting.show_backtest import show_backtest

from backtesting.advanced_backtest import advanced_backtest
from backtesting.show_advanced_backtest import show_advanced_backtest

from structure.order_blocks import detect_order_blocks
from structure.show_order_blocks import show_order_blocks

from structure.liquidity import detect_liquidity
from structure.show_liquidity import show_liquidity

from structure.fvg import detect_fvg
from structure.show_fvg import show_fvg

from structure.premium_discount import get_pd_zone
from structure.show_pd_zone import show_pd_zone

from backtesting.advanced_backtest_v2 import advanced_backtest_v2
from backtesting.show_advanced_backtest_v2 import (
    show_advanced_backtest_v2
)

from reports.recommendation import (
    show_recommendation
)

from reports.trade_journal import (
    save_trade_journal
)

from reports.export_report import (
    export_report
)

from dashboard.dashboard import (
    generate_dashboard
)

from dashboard.history_dashboard import (
    create_history_dashboard
)

from paper_trading.trade_manager import (
    open_virtual_trade
)


def seleccionar_activo():

    activos = {

        1: "BTC-USD",
        2: "ETH-USD",
        3: "SOL-USD",
        4: "SPY",
        5: "QQQ"

    }

    print(
        "\n=========== SELECCION DE ACTIVO ===========\n"
    )

    print("1. BTC-USD")
    print("2. ETH-USD")
    print("3. SOL-USD")
    print("4. SPY")
    print("5. QQQ")
    print("6. ANALIZAR TODOS")
    print("0. SALIR")

    while True:

        try:

            opcion = int(
                input(
                    "\nSeleccione una opcion: "
                )
            )

            if opcion in [0, 1, 2, 3, 4, 5, 6]:

                return opcion, activos

            print(
                "\nOpcion invalida"
            )

        except:

            print(
                "\nIngrese un numero valido"
            )


def analizar_activo(SYMBOL):

    print("\nMARKET ANALYZER\n")

    ACCOUNT_SIZE = 10000
    RISK_PERCENT = 1

    # =====================
    # DATOS
    # =====================

    df = load_data(
        SYMBOL,
        PERIOD,
        INTERVAL
    )

    # =====================
    # INDICADORES
    # =====================

    df = calculate_ema(
        df,
        EMA_FAST
    )

    df = calculate_ema(
        df,
        EMA_SLOW
    )

    df = calculate_rsi(df)

    df = calculate_macd(df)

    df = calculate_atr(df)

    df = calculate_adx(df)

    df = calculate_volume_ma(df)

    df = calculate_relative_volume(df)

    volume_signal = get_volume_signal(df)

    # =====================
    # ESTRUCTURA
    # =====================

    df = detect_swings(df)

    show_structure(df)

    highs, lows = classify_structure(df)

    show_hh_hl(
        highs,
        lows
    )

    market_structure = get_market_structure(df)

    bos = detect_bos(df)

    choch = detect_choch(df)

    order_blocks = detect_order_blocks(df)

    liquidity = detect_liquidity(df)

    fvg = detect_fvg(df)

    pd_zone = get_pd_zone(df)

    show_order_blocks(order_blocks)

    show_liquidity(liquidity)

    show_fvg(fvg)

    show_pd_zone(pd_zone)

    support = get_support(df)

    resistance = get_resistance(df)

    # =====================
    # FIBONACCI
    # =====================

    fib_levels = calculate_fibonacci(df)

    show_fibonacci(
        fib_levels
    )

    fib_zone = get_fibonacci_zone(
        float(df["Close"].iloc[-1]),
        fib_levels
    )

    # =====================
    # TENDENCIA
    # =====================

    trend = get_trend(df)

    score = calculate_score(df)

    signal = get_signal(score)

    # =====================
    # CONFLUENCIAS
    # =====================

    conf_score, factors = analyze_confluence(
        trend,
        market_structure,
        bos,
        choch,
        fib_zone,
        df
    )

    # =====================
    # TRADE PLAN
    # =====================

    trade_plan = calculate_trade_plan(
        float(df["Close"].iloc[-1]),
        float(support),
        float(resistance),
        float(df["ATR"].iloc[-1]),
        signal
    )

    # =====================
    # POSITION SIZE
    # =====================

    position = calculate_position_size(
        ACCOUNT_SIZE,
        RISK_PERCENT,
        trade_plan["entry"],
        trade_plan["stop"]
    )

    # =====================
    # BACKTESTS
    # =====================

    backtest_result = simple_backtest(df)

    advanced_result = advanced_backtest(df)

    advanced_v2_result = advanced_backtest_v2(df)

    ultimo = df.iloc[-1]

    # =====================
    # RESULTADO
    # =====================

    print(
        "\n=========== RESULTADO ==========="
    )

    print(
        "Tendencia  :",
        trend
    )

    print(
        "Estructura :",
        market_structure
    )

    print(
        "BOS        :",
        bos
    )

    print(
        "CHOCH      :",
        choch
    )

    print(
        "Soporte    :",
        round(float(support), 2)
    )

    print(
        "Resistencia:",
        round(float(resistance), 2)
    )

    print(
        "Zona Fib   :",
        fib_zone
    )

    print(
        "Volumen    :",
        volume_signal
    )

    print(
        "Score      :",
        score
    )

    print(
        "Señal      :",
        signal
    )

    # =====================
    # TRADE PLAN
    # =====================

    print(
        "\n=========== TRADE PLAN ==========="
    )

    print(
        "Entrada     :",
        round(trade_plan["entry"], 2)
    )

    print(
        "Stop Loss   :",
        round(trade_plan["stop"], 2)
    )

    print(
        "TP1         :",
        round(trade_plan["tp1"], 2)
    )

    print(
        "TP2         :",
        round(trade_plan["tp2"], 2)
    )

    print(
        "TP3         :",
        round(trade_plan["tp3"], 2)
    )

    print(
        "Risk/Reward :",
        round(trade_plan["rr"], 2)
    )

    # =====================
    # POSITION SIZE
    # =====================

    if position is not None:

        print(
            "\n=========== POSITION SIZE ==========="
        )

        print(
            "Capital     :",
            round(position["account_size"], 2)
        )

        print(
            "Riesgo %    :",
            round(position["risk_percent"], 2)
        )

        print(
            "Riesgo Max  :",
            round(position["risk_amount"], 2)
        )

        print(
            "Posicion    :",
            round(
                position["position_size"],
                6
            )
        )

    # =====================
    # CONFLUENCIAS
    # =====================

    show_confluence(
        conf_score,
        factors
    )

    # =====================
    # BACKTESTS
    # =====================

    show_backtest(
        backtest_result
    )

    show_advanced_backtest(
        advanced_result
    )

    show_advanced_backtest_v2(
        advanced_v2_result
    )

    # =====================
    # INDICADORES
    # =====================

    print(
        "\n=========== INDICADORES ==========="
    )

    print(
        "RSI         :",
        round(
            float(ultimo["RSI"]),
            2
        )
    )

    print(
        "ADX         :",
        round(
            float(ultimo["ADX"]),
            2
        )
    )

    print(
        "ATR         :",
        round(
            float(ultimo["ATR"]),
            2
        )
    )

    print(
        "MACD        :",
        round(
            float(ultimo["MACD"]),
            2
        )
    )

    print(
        "MACD Signal :",
        round(
            float(
                ultimo["MACD_SIGNAL"]
            ),
            2
        )
    )

    print(
        "VOL MA      :",
        round(
            float(
                ultimo["VOL_MA"]
            ),
            0
        )
    )

    print(
        "RVOL        :",
        round(
            float(
                ultimo["RVOL"]
            ),
            2
        )
    )

    # =====================
    # ULTIMA VELA
    # =====================

    print(
        "\n=========== ULTIMA VELA ==========="
    )

    print(
        "Fecha  :",
        ultimo["Date"]
    )

    print(
        "Open   :",
        round(
            float(
                ultimo["Open"]
            ),
            2
        )
    )

    print(
        "High   :",
        round(
            float(
                ultimo["High"]
            ),
            2
        )
    )

    print(
        "Low    :",
        round(
            float(
                ultimo["Low"]
            ),
            2
        )
    )

    print(
        "Close  :",
        round(
            float(
                ultimo["Close"]
            ),
            2
        )
    )

    print(
        "Volume :",
        int(
            ultimo["Volume"]
        )
    )

    # =====================
    # RECOMENDACION FINAL
    # =====================

    if conf_score >= 90:

        probability = "EXTREMA"

    elif conf_score >= 75:

        probability = "MUY ALTA"

    elif conf_score >= 60:

        probability = "ALTA"

    elif conf_score >= 40:

        probability = "MEDIA"

    else:

        probability = "BAJA"

    # =====================
    # RECOMENDACION
    # =====================

    show_recommendation(
        SYMBOL,
        signal,
        probability,
        trade_plan,
        advanced_v2_result
    )

    # =====================
    # PAPER TRADING
    # =====================

    if (
        probability in ["MUY ALTA", "EXTREMA"]
        and
        advanced_v2_result["profit_factor"] >= 1.8
    ):

        open_virtual_trade(
            SYMBOL,
            signal,
            trade_plan
        )

    # =====================
    # JOURNAL
    # =====================

    save_trade_journal(
        SYMBOL,
        signal,
        probability,
        trade_plan
    )

    create_history_dashboard()

    # =====================
    # REPORTE TXT
    # =====================

    export_report(
        SYMBOL,
        signal,
        conf_score,
        trade_plan,
        advanced_v2_result
    )

    # =====================
    # DASHBOARD
    # =====================

    generate_dashboard(
        advanced_v2_result
    )


if __name__ == "__main__":

    while True:

        opcion, activos = seleccionar_activo()

        # =====================
        # SALIR
        # =====================

        if opcion == 0:

            print(
                "\nFinalizando Market Analyzer..."
            )

            break

        # =====================
        # ANALIZAR TODOS
        # =====================

        elif opcion == 6:

            for simbolo in activos.values():

                print(
                    "\n" + "=" * 80
                )

                print(
                    f"ANALIZANDO {simbolo}"
                )

                print(
                    "=" * 80
                )

                analizar_activo(
                    simbolo
                )

        # =====================
        # ACTIVO INDIVIDUAL
        # =====================

        else:

            analizar_activo(
                activos[opcion]
            )