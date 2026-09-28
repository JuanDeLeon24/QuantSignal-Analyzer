import pandas as pd

from structure.bos_signal import bos_bullish
from structure.choch_signal import choch_bullish
from structure.fibonacci import calculate_fibonacci
from structure.fib_backtest import fib_confluence


SWING_CONFIRMATION = 3  # velas necesarias para confirmar un swing (window de detect_swings)


def advanced_backtest_v2(df, initial_equity=10000.0, risk_pct=0.1):
    """
    Backtest LONG con score de confluencias.

    Cambios v2.1:
      - El PnL de las operaciones que vencen por tiempo se escala al riesgo
        (antes se sumaba la diferencia de precio de 1 unidad y en BTC eso
        inflaba el retorno y el profit factor).
      - Fibonacci se calcula solo con swings ya confirmados en la vela i
        (antes usaba todo el historico: sesgo de mirar al futuro).
      - Devuelve la lista de operaciones y la curva de equity real.
    """

    equity = float(initial_equity)
    equity_peak = equity

    max_drawdown = 0.0

    trades = 0
    wins = 0
    losses = 0

    gross_profit = 0.0
    gross_loss = 0.0

    trade_log = []
    equity_curve = [equity]
    drawdown_curve = [0.0]

    last_trade_index = -999

    has_date = "Date" in df.columns

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

        ema_ok = ema50 > ema200

        if ema_ok:
            score += 2

        if rsi > 50:
            score += 1

        if adx > 35:
            score += 1

        if rvol > 1.3:
            score += 1

        bos_ok = bos_bullish(df, i)

        if bos_ok:
            score += 2

        choch_ok = choch_bullish(df, i)

        if choch_ok:
            score += 2

        # Fibonacci sin mirar al futuro

        fib_ok = False

        if score >= 5:

            visible = df.iloc[: max(0, i - SWING_CONFIRMATION + 1)]

            fib_levels = None

            if (
                len(visible) > 0
                and visible["Swing_High"].sum() >= 2
                and visible["Swing_Low"].sum() >= 1
            ):
                fib_levels = calculate_fibonacci(visible)

            if fib_levels is not None:
                fib_ok = fib_confluence(close_price, fib_levels)

        if fib_ok:
            score += 1

        if score < 6:
            continue

        market_bias = int(ema_ok) + int(bos_ok) + int(choch_ok)

        if market_bias < 2:
            continue

        entry = close_price

        stop = entry - (atr * 3)

        risk = entry - stop

        target = entry + (risk * 2)

        risk_amount = equity * risk_pct / 100

        last_trade_index = i

        trades += 1

        trade_result = None
        exit_price = None
        exit_index = None

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
                trade_result = "LOSS"
                exit_price = stop
                exit_index = j
                break

            if high >= target:

                pnl = risk_amount * 2
                trade_result = "WIN"
                exit_price = target
                exit_index = j
                break

        if trade_result is None:

            close_out = float(df["Close"].iloc[future_limit])

            pnl = risk_amount * (close_out - entry) / risk

            trade_result = "TIMEOUT"
            exit_price = close_out
            exit_index = future_limit

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

        max_drawdown = max(max_drawdown, drawdown)

        equity_curve.append(equity)
        drawdown_curve.append(drawdown)

        trade_log.append({
            "entry_index": i,
            "exit_index": exit_index,
            "entry_time": df["Date"].iloc[i] if has_date else i,
            "exit_time": df["Date"].iloc[exit_index] if has_date else exit_index,
            "entry": entry,
            "stop": stop,
            "target": target,
            "exit": exit_price,
            "result": trade_result,
            "score": score,
            "r_multiple": pnl / risk_amount if risk_amount else 0.0,
            "pnl": pnl,
            "equity": equity,
        })

    win_rate = (wins / trades * 100) if trades else 0.0

    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0

    expectancy = ((gross_profit - gross_loss) / trades) if trades else 0.0

    avg_r = (
        sum(t["r_multiple"] for t in trade_log) / trades
        if trades else 0.0
    )

    return {

        "trades": trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "expectancy": round(expectancy, 2),
        "expectancy_r": round(avg_r, 3),
        "equity": round(equity, 2),
        "return_pct": round(
            (equity - initial_equity) / initial_equity * 100,
            2
        ),
        "max_drawdown": round(max_drawdown, 2),

        "trade_log": trade_log,
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
    }
