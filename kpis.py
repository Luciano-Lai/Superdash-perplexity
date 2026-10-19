import streamlit as st
import pandas as pd


def calculate_kpis(df):
    total = len(df)

    preventivas = len(df[df["Tipo"] == "Preventiva"])
    corretivas = len(df[df["Tipo"] == "Corretiva"])

    if total > 0:
        perc_preventivas = f"{(preventivas / total * 100):.1f}%"
        perc_corretivas = f"{(corretivas / total * 100):.1f}%"
    else:
        perc_preventivas = "—"
        perc_corretivas = "—"

    maquinas = df["Máquina"].nunique()
    tecnicos = df["Técnico"].nunique()

    df_corretivas = df[df["Tipo"] == "Corretiva"]

    em_garantia = len(
        df_corretivas[df_corretivas["Garantia"] == "Dentro"]
    )

    fora_garantia = len(
        df_corretivas[df_corretivas["Garantia"] == "Fora"]
    )

    problemas = (
        df_corretivas["Problema"]
        .dropna()
        .astype(str)
        .str.split(";")
        .explode()
        .str.strip()
    )

    problemas = problemas[
        ~problemas.str.lower().isin([
            "não informado",
            "nao informado",
        ])
    ]

    if problemas.empty:
        problema_mais_frequente = "—"
    else:
        problema_mais_frequente = problemas.mode()[0]

    pecas = (
        df["Peça"]
        .dropna()
        .astype(str)
        .str.split(";")
        .explode()
        .str.strip()
    )

    pecas = pecas[
        ~pecas.str.lower().isin([
            "nenhuma",
            "não informado",
            "nao informado",
        ])
    ]

    if pecas.empty:
        peca_mais_trocada = "—"
    else:
        peca_mais_trocada = pecas.mode()[0]

    return {
        "Total de tarefas": total,
        "Preventivas": preventivas,
        "Corretivas": corretivas,
        "% Preventivas": perc_preventivas,
        "% Corretivas": perc_corretivas,
        "Máquinas atendidas": maquinas,
        "Técnicos envolvidos": tecnicos,
        "Corretivas em garantia": em_garantia,
        "Corretivas fora da garantia": fora_garantia,
        "Problema mais frequente": problema_mais_frequente,
        "Peça mais trocada": peca_mais_trocada,
    }


def render_kpi_cards(selected_kpis, kpi_values):
    if not selected_kpis:
        return

    for inicio in range(0, len(selected_kpis), 4):
        grupo = selected_kpis[inicio:inicio + 4]
        colunas = st.columns(len(grupo))

        for coluna, nome_kpi in zip(colunas, grupo):
            valor = kpi_values.get(nome_kpi, "—")

            with coluna:
                st.metric(
                    label=nome_kpi,
                    value=valor,
                )
