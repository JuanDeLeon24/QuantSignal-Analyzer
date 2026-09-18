import pandas as pd

from structure.bos_signal import bos_bullish
from structure.choch_signal import choch_bullish
from structure.fibonacci import calculate_fibonacci
from structure.fib_backtest import fib_confluence


def advanced_backtest_v2(df):

    initial_equity = 10000.0

    equity = initial_equity
    equity_peak = equity

    max_drawdown = 0.0

    trades = 0
    wins = 0
    losses = 0

    gross_profit = 0.0
    gross_loss = 0.0

    fib_levels = calculate_fibonacci(df)

    last_trade_index = -999

    for i in range(200, len(df) - 20):

        # Cooldown de 30 velas

        if i - last_trade_index < 30:
            continue

        ema50 = df["EMA_50"].iloc[i]
        ema200 = df["EMA_200"].iloc[i]

        rsi = df["RSI"].iloc[i]
        adx = df["ADX"].iloc[i]
        rvol = df["RVOL"].iloc[i]

        atr = df["ATR"].iloc[i]

        if (
            pd.isna(ema50)
            or pd.isna(ema200)
            or pd.isna(rsi)
            or pd.isna(adx)
            or pd.isna(rvol)
            or pd.isna(atr)
        ):
            continue

        close_price = float(
            df["Close"].iloc[i]
        )

        score = 0

        # EMA

        ema_ok = ema50 > ema200

        if ema_ok:
            score += 2

        # RSI

        if rsi > 50:
            score += 1

        # ADX

        if adx > 35:
            score += 1

        # RVOL

        if rvol > 1.3:
            score += 1

        # BOS

        bos_ok = bos_bullish(df, i)

        if bos_ok:
            score += 2

        # CHOCH

        choch_ok = choch_bullish(df, i)

        if choch_ok:
            score += 2

        # FIB

        fib_ok = fib_confluence(
            close_price,
            fib_levels
        )

        if fib_ok:
            score += 1

        # Score mínimo

        if score < 6:
            continue

        # Market Bias

        market_bias = 0

        if ema_ok:
            market_bias += 1

        if bos_ok:
            market_bias += 1

        if choch_ok:
            market_bias += 1

        if market_bias < 2:
            continue

        entry = close_price

        # Stop más amplio

        stop = entry - (atr * 3)

        risk = entry - stop

        # RR 2:1

        target = entry + (risk * 2)

        risk_amount = equity * 0.001

        last_trade_index = i

        trades += 1

        trade_result = None

        future_limit = min(
            i + 20,
            len(df) - 1
        )

        for j in range(
            i + 1,
            future_limit + 1
        ):

            high = float(
                df["High"].iloc[j]
            )

            low = float(
                df["Low"].iloc[j]
            )

            if low <= stop:

                pnl = -risk_amount

                losses += 1

                gross_loss += abs(pnl)

                equity += pnl

                trade_result = "LOSS"

                break

            if high >= target:

                pnl = risk_amount * 2

                wins += 1

                gross_profit += pnl

                equity += pnl

                trade_result = "WIN"

                break

        if trade_result is None:

            close_out = float(
                df["Close"].iloc[
                    future_limit
                ]
            )

            pnl = close_out - entry

            equity += pnl

            if pnl > 0:

                wins += 1

                gross_profit += pnl

            else:

                losses += 1

                gross_loss += abs(pnl)

        equity_peak = max(
            equity_peak,
            equity
        )

        drawdown = (
            (equity_peak - equity)
            /
            equity_peak
        ) * 100

        max_drawdown = max(
            max_drawdown,
            drawdown
        )

    win_rate = 0.0

    if trades > 0:

        win_rate = (
            wins / trades
        ) * 100

    profit_factor = 0.0

    if gross_loss > 0:

        profit_factor = (
            gross_profit
            /
            gross_loss
        )

    expectancy = 0.0

    if trades > 0:

        expectancy = (
            gross_profit
            - gross_loss
        ) / trades

    return {

        "trades": trades,

        "wins": wins,

        "losses": losses,

        "win_rate": round(
            win_rate,
            2
        ),

        "profit_factor": round(
            profit_factor,
            2
        ),

        "gross_profit": round(
            gross_profit,
            2
        ),

        "gross_loss": round(
            gross_loss,
            2
        ),

        "expectancy": round(
            expectancy,
            2
        ),

        "equity": round(
            equity,
            2
        ),

        "return_pct": round(
            (
                equity
                - initial_equity
            )
            /
            initial_equity
            * 100,
            2
        ),

        "max_drawdown": round(
            max_drawdown,
            2
        )
    }