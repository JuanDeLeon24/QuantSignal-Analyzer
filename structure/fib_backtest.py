def fib_confluence(
    close_price,
    fib_levels
):

    fib_236 = fib_levels["0.236"]
    fib_382 = fib_levels["0.382"]
    fib_500 = fib_levels["0.500"]
    fib_618 = fib_levels["0.618"]

    if fib_236 >= close_price >= fib_618:
        return True

    if fib_382 >= close_price >= fib_618:
        return True

    if fib_500 >= close_price >= fib_618:
        return True

    return False