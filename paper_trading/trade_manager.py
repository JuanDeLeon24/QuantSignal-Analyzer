import csv
import os
import pandas as pd

from datetime import datetime


def trade_exists(
    symbol,
    signal
):

    if not os.path.exists(
        "trades.csv"
    ):
        return False

    try:

        df = pd.read_csv(
            "trades.csv"
        )

        abiertas = df[
            (df["activo"] == symbol)
            &
            (df["senal"] == signal)
            &
            (df["estado"] == "ABIERTA")
        ]

        return len(abiertas) > 0

    except Exception:

        return False


def get_next_id():

    if not os.path.exists(
        "trades.csv"
    ):
        return 1

    try:

        df = pd.read_csv(
            "trades.csv"
        )

        if len(df) == 0:
            return 1

        return int(
            df["id"].max()
        ) + 1

    except Exception:

        return 1


def open_virtual_trade(
    symbol,
    signal,
    trade_plan
):

    if trade_exists(
        symbol,
        signal
    ):

        print(
            "\n⚠ Ya existe una operacion abierta para este activo"
        )

        return

    trade_id = get_next_id()

    with open(
        "trades.csv",
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(
            file
        )

        writer.writerow([

            trade_id,

            datetime.now().strftime(
                "%d/%m/%Y %H:%M"
            ),

            symbol,

            signal,

            trade_plan["entry"],

            trade_plan["stop"],

            trade_plan["tp1"],

            trade_plan["tp2"],

            trade_plan["tp3"],

            "ABIERTA",

            trade_plan["entry"],

            0,

            ""

        ])

    print(
        f"\n✅ Operacion virtual creada -> ID {trade_id}"
    )