def calculate_position_size(
    account_size,
    risk_percent,
    entry,
    stop
):

    risk_amount = (
        account_size
        * risk_percent
        / 100
    )

    risk_per_unit = abs(
        entry - stop
    )

    if risk_per_unit <= 0:

        return None

    position_size = (
        risk_amount
        / risk_per_unit
    )

    return {
        "account_size": account_size,
        "risk_percent": risk_percent,
        "risk_amount": risk_amount,
        "risk_per_unit": risk_per_unit,
        "position_size": position_size,
        "notional": position_size * entry,
    }
