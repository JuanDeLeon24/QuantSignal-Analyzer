import yfinance as yf

def load_data(symbol, period, interval):

    df = yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False
    )

    # Elimina el segundo nivel del MultiIndex
    if hasattr(df.columns, "droplevel"):
        try:
            df.columns = df.columns.droplevel(1)
        except:
            pass

    df.reset_index(inplace=True)

    return df