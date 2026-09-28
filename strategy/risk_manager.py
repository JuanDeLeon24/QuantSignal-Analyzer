def signal_direction(signal):
    """
    Convierte la senal textual en direccion operable.
    "LONG" y "LONG FUERTE" -> LONG ; "SHORT" y "SHORT FUERTE" -> SHORT ;
    cualquier otra ("ESPERAR") -> NONE
    """

    signal = str(signal).upper()

    if signal.startswith("LONG"):
        return "LONG"

    if signal.startswith("SHORT"):
        return "SHORT"

    return "NONE"


def calculate_trade_plan(
    entry,
    support,
    resistance,
    atr,
    signal="LONG"
):

    rr = 2.5

    entry = float(entry)
    atr = float(atr)

    support = float(support) if support is not None else entry - atr * 2
    resistance = float(resistance) if resistance is not None else entry + atr * 2

    direction = signal_direction(signal)

    # Si la senal es ESPERAR se calcula un plan LONG solo como referencia
    plan_side = "SHORT" if direction == "SHORT" else "LONG"

    # ==================================
    # LONG
    # ==================================

    if plan_side == "LONG":

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

        "direction": direction,

        "plan_side": plan_side,

        "entry": round(entry, 2),

        "stop": round(stop, 2),

        "risk": round(risk, 2),

        "tp1": round(tp1, 2),

        "tp2": round(tp2, 2),

        "tp3": round(tp3, 2),

        "rr": round(rr, 2)

    }
