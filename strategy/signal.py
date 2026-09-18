def get_signal(score):

    if score >= 80:
        return "LONG FUERTE"

    elif score >= 60:
        return "LONG"

    elif score >= 40:
        return "ESPERAR"

    elif score >= 20:
        return "SHORT"

    else:
        return "SHORT FUERTE"