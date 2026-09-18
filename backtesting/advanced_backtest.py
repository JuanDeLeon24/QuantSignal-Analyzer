import pandas as pd


def advanced_backtest(df):

    initial_equity = 10000.0

    equity = initial_equity
    equity_peak = equity

    max_drawdown = 0.0

    trades = 0
    wins = 0
    losses = 0

    gross_profit = 0.0
    gross_loss = 0.0

    for i in range(200, len(df) - 20):

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

        score = 0

        if ema50 > ema200:
            score += 1

        if rsi > 50:
            score += 1

        if adx > 35:
            score += 1

        if rvol > 1.4:
            score += 1

        if score != 4:
            continue

        entry = float(df["Close"].iloc[i])

        stop = entry - (atr * 2)

        risk = entry - stop

        target = entry + (risk * 1.5)

        risk_amount = equity * 0.002

        trades += 1

        result = None

        future_limit = min(
            i + 20,
            len(df) - 1
        )

        for j in range(
            i + 1,
            future_limit + 1
        ):

            high = float(df["High"].iloc[j])
            low = float(df["Low"].iloc[j])

            if low <= stop:

                pnl = -risk_amount

                losses += 1

                gross_loss += abs(pnl)

                equity += pnl

                result = "LOSS"

                break

            if high >= target:

                pnl = risk_amount * 1.5

                wins += 1

                gross_profit += pnl

                equity += pnl

                result = "WIN"

                break

        if result is None:

            close_out = float(
                df["Close"].iloc[future_limit]
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
            (
                equity_peak - equity
            )
            / equity_peak
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
            -
            gross_loss
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
                equity - initial_equity
            )
            / initial_equity
            * 100,
            2
        ),

        "max_drawdown": round(
            max_drawdown,
            2
        )
    }