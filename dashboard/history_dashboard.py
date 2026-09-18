import matplotlib
matplotlib.use("Agg")

import pandas as pd
import matplotlib.pyplot as plt


def create_history_dashboard():

    df = pd.read_csv(
        "trade_journal.csv"
    )

    fig, ax = plt.subplots(
        2,
        2,
        figsize=(16, 10)
    )

    # -------------------------
    # ENTRADAS
    # -------------------------

    for activo in df["activo"].unique():

        temp = df[
            df["activo"] == activo
        ]

        ax[0, 0].plot(
            temp.index,
            temp["entrada"],
            marker="o",
            label=activo
        )

    ax[0, 0].set_title(
        "Entradas Historicas"
    )

    ax[0, 0].legend()

    # -------------------------
    # TP3
    # -------------------------

    ultimo = (
        df.groupby("activo")
        .last()
        .reset_index()
    )

    ax[0, 1].bar(

        ultimo["activo"],

        ultimo["tp3"],

        color="green"
    )

    ax[0, 1].set_title(
        "Ultimos TP3"
    )

    # -------------------------
    # PROBABILIDADES
    # -------------------------

    df["probabilidad"].value_counts().plot(

        kind="bar",

        ax=ax[1, 0],

        color="orange"
    )

    ax[1, 0].set_title(
        "Distribucion de Probabilidades"
    )

    # -------------------------
    # LONG / SHORT
    # -------------------------

    df["senal"].value_counts().plot(

        kind="pie",

        ax=ax[1, 1],

        autopct="%1.1f%%"
    )

    ax[1, 1].set_ylabel("")

    ax[1, 1].set_title(
        "Long vs Short"
    )

    plt.tight_layout()

    plt.savefig(
        "trade_journal_dashboard.png"
    )

    plt.close()

    print(
        "\n✅ Dashboard historico generado"
    )

    print(
        "trade_journal_dashboard.png"
    )