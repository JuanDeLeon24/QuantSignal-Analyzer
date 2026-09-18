import csv
import os

from datetime import datetime


def save_trade_journal(
    symbol,
    signal,
    probability,
    trade_plan
):

    file_name = "trade_journal.csv"

    file_exists = os.path.exists(
        file_name
    )

    with open(
        file_name,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        if not file_exists:

            writer.writerow([

                "fecha",

                "activo",

                "senal",

                "probabilidad",

                "entrada",

                "stop",

                "tp1",

                "tp2",

                "tp3",

                "rr"

            ])

        writer.writerow([

            datetime.now(),

            symbol,

            signal,

            probability,

            trade_plan["entry"],

            trade_plan["stop"],

            trade_plan["tp1"],

            trade_plan["tp2"],

            trade_plan["tp3"],

            trade_plan["rr"]

        ])

    print(
        "\n✅ Trade Journal actualizado"
    )