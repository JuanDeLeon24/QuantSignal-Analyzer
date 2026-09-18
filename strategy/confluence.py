def analyze_confluence(
    trend,
    market_structure,
    bos,
    choch,
    fib_zone,
    df
):

    score = 0

    factors = []

    ultimo = df.iloc[-1]

    if trend == "BULLISH":

        score += 20

        factors.append(
            "✅ EMA Alcista"
        )

    else:

        score -= 20

    if ultimo["RSI"] > 50:

        score += 10

        factors.append(
            "✅ RSI Alcista"
        )

    if ultimo["ADX"] > 25:

        score += 15

        factors.append(
            "✅ ADX Fuerte"
        )

    if bos == "BULLISH BOS":

        score += 20

        factors.append(
            "✅ BOS Alcista"
        )

    if choch == "BULLISH CHOCH":

        score += 15

        factors.append(
            "✅ CHOCH Alcista"
        )

    if fib_zone != "FUERA":

        score += 10

        factors.append(
            "✅ Zona Fibonacci"
        )

    if ultimo["RVOL"] > 1.2:

        score += 10

        factors.append(
            "✅ Volumen Confirmado"
        )

    if market_structure == "DOWNTREND":

        score -= 15

    score = max(0, min(score, 100))

    return score, factors