def detect_choch(df):
    """
    Change of Character: ruptura EN CONTRA de la estructura vigente.

      - Estructura bajista (LH + LL) y el cierre supera el ultimo swing high
        -> BULLISH CHOCH (posible giro al alza)
      - Estructura alcista (HH + HL) y el cierre pierde el ultimo swing low
        -> BEARISH CHOCH (posible giro a la baja)

    (La version anterior era identica a detect_bos: cualquier ruptura contaba
    como CHOCH, por lo que la confluencia sumaba dos veces la misma senal.)
    """

    highs = df[df["Swing_High"] == True]  # noqa: E712
    lows = df[df["Swing_Low"] == True]  # noqa: E712

    if len(highs) < 2 or len(lows) < 2:
        return "NO CHOCH"

    last_close = df["Close"].iloc[-1]

    last_high, prev_high = highs["High"].iloc[-1], highs["High"].iloc[-2]
    last_low, prev_low = lows["Low"].iloc[-1], lows["Low"].iloc[-2]

    downtrend = last_high < prev_high and last_low < prev_low
    uptrend = last_high > prev_high and last_low > prev_low

    if downtrend and last_close > last_high:
        return "BULLISH CHOCH"

    if uptrend and last_close < last_low:
        return "BEARISH CHOCH"

    return "NO CHOCH"
