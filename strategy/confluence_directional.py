"""
Confluencia DIRECCIONAL (simetrica para LONG y SHORT).

La confluencia original (strategy/confluence.py) solo sumaba factores
alcistas: una senal SHORT siempre salia con probabilidad "BAJA" aunque
todo estuviera alineado a la baja. Esta version evalua la direccion
de la senal.
"""


def analyze_confluence_directional(direction, trend, market_structure, bos, choch,
                                   fib_zone, pd_zone, liquidity, df):

    u = df.iloc[-1]
    long = direction != "SHORT"
    score = 0
    factors = []
    against = []

    def add(ok, pts, text_ok, text_bad=None):
        nonlocal score
        if ok:
            score += pts
            factors.append(text_ok)
        elif text_bad:
            against.append(text_bad)

    add(trend == ("BULLISH" if long else "BEARISH"), 20,
        "Tendencia EMA50/200 a favor", "Tendencia EMA50/200 en contra")
    add(market_structure == ("UPTREND" if long else "DOWNTREND"), 15,
        "Estructura HH/HL a favor" if long else "Estructura LH/LL a favor",
        "Estructura de mercado no confirma")
    add((u["RSI"] > 50) if long else (u["RSI"] < 50), 10, "Momentum RSI a favor", "RSI en contra")
    add((u["MACD"] > u["MACD_SIGNAL"]) if long else (u["MACD"] < u["MACD_SIGNAL"]), 10,
        "MACD a favor", "MACD en contra")
    add(u["ADX"] > 25, 10, "Tendencia con fuerza (ADX > 25)", "ADX debil: mercado sin direccion")
    add(bos == ("BULLISH BOS" if long else "BEARISH BOS"), 10, "Ruptura de estructura (BOS) a favor")
    add(choch == ("BULLISH CHOCH" if long else "BEARISH CHOCH"), 10, "Cambio de caracter (CHOCH) a favor")
    add(pd_zone == ("DISCOUNT" if long else "PREMIUM"), 5,
        "Precio en zona de descuento" if long else "Precio en zona premium",
        "Precio en zona cara para entrar" if long else "Precio en zona barata para vender")
    add(liquidity == ("BULLISH_SWEEP" if long else "BEARISH_SWEEP"), 5, "Barrido de liquidez a favor")
    add(isinstance(fib_zone, str) and any(k in fib_zone for k in ("0.382", "0.500", "0.618")), 5,
        "Precio en zona Fibonacci 38-62%")
    add(u["RVOL"] > 1.2, 5, "Volumen confirma (RVOL > 1.2)", "Volumen bajo")

    if (trend == "BEARISH" and long) or (trend == "BULLISH" and not long):
        score -= 10

    return max(0, min(100, score)), factors, against
