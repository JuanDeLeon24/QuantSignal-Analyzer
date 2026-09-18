def get_volume_signal(df):

    rvol = df["RVOL"].iloc[-1]

    if rvol >= 2:
        return "VOLUMEN EXTREMO"

    if rvol >= 1.5:
        return "VOLUMEN ALTO"

    if rvol >= 1:
        return "VOLUMEN NORMAL"

    return "VOLUMEN BAJO"
