def calculate_trade_plan(
    entry,
    support,
    resistance,
    atr,
    signal="LONG"
):

    rr = 2.5

    entry = float(entry)
    support = float(support)
    resistance = float(resistance)
    atr = float(atr)

    # ==================================
    # LONG
    # ==================================

    if signal == "LONG":

        stop = min(
            support,
            entry - (atr * 1.5)
        )

        risk = entry - stop

        if risk <= 0:

            stop = entry - (atr * 2)

            risk = entry - stop

        tp1 = entry + risk

        tp2 = entry + (risk * 2)

        tp3 = entry + (risk * rr)

    # ==================================
    # SHORT
    # ==================================

    else:

        stop = max(
            resistance,
            entry + (atr * 1.5)
        )

        risk = stop - entry

        if risk <= 0:

            stop = entry + (atr * 2)

            risk = stop - entry

        tp1 = entry - risk

        tp2 = entry - (risk * 2)

        tp3 = entry - (risk * rr)

    return {

        "entry": round(entry, 2),

        "stop": round(stop, 2),

        "risk": round(risk, 2),

        "tp1": round(tp1, 2),

        "tp2": round(tp2, 2),

        "tp3": round(tp3, 2),

        "rr": round(rr, 2)

    }