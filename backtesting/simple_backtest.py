import pandas as pd


def simple_backtest(df):

    trades = 0
    wins = 0
    losses = 0

    gross_profit = 0.0
    gross_loss = 0.0

    equity = 10000.0
    equity_peak = equity
    max_drawdown = 0.0

    risk_pct = 1

    for i in range(200, len(df) - 20):

        ema50 = df["EMA_50"].iloc[i]
        ema200 = df["EMA_200"].iloc[i]

        rsi = df["RSI"].iloc[i]
        adx = df["ADX"].iloc[i]

        if (
            pd.isna(ema50)
            or pd.isna(ema200)
            or pd.isna(rsi)
            or pd.isna(adx)
        ):
            continue

        # FILTROS

        if ema50 <= ema200:
            continue

        if rsi <= 50:
            continue

        if adx <= 20:
            continue

        entry = float(df["Close"].iloc[i])

        stop = entry * 0.97
        target = entry * 1.06

        risk_amount = equity * (risk_pct / 100)

        trades += 1

        trade_result = None

        for j in range(i + 1, min(i + 21, len(df))):

            high = float(df["High"].iloc[j])
            low = float(df["Low"].iloc[j])

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

            close_out = float(df["Close"].iloc[j])

            pnl = close_out - entry

            if pnl > 0:

                wins += 1
                gross_profit += pnl

            else:

                losses += 1
                gross_loss += abs(pnl)

            equity += pnl

        equity_peak = max(equity_peak, equity)

        drawdown = (
            (equity_peak - equity)
            / equity_peak
        ) * 100

        max_drawdown = max(
            max_drawdown,
            drawdown
        )

    win_rate = 0

    if trades > 0:
        win_rate = (
            wins / trades
        ) * 100

    profit_factor = 0

    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss

    expectancy = 0

    if trades > 0:
        expectancy = (
            gross_profit - gross_loss
        ) / trades

    return {

        "trades": trades,

        "wins": wins,

        "losses": losses,

        "win_rate": round(win_rate, 2),

        "profit_factor": round(profit_factor, 2),

        "gross_profit": round(gross_profit, 2),

        "gross_loss": round(gross_loss, 2),

        "expectancy": round(expectancy, 2),

        "final_equity": round(equity, 2),

        "return_pct": round(
            ((equity - 10000) / 10000) * 100,
            2
        ),

        "max_drawdown": round(max_drawdown, 2)
    }