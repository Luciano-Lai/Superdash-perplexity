import streamlit as st
import pandas as pd

KPI_STYLES = {
    "Total de tarefas": {
        "icon": "📋",
        "color": "#1F4E79",
        "background": "#EFF6FF",
    },
    "Preventivas": {
        "icon": "🛠️",
        "color": "#2E86AB",
        "background": "#E8F4F8",
    },
    "Corretivas": {
        "icon": "⚠️",
        "color": "#E76F51",
        "background": "#FFF1EC",
    },
    "% Preventivas": {
        "icon": "📈",
        "color": "#2E86AB",
        "background": "#E8F4F8",
    },
    "% Corretivas": {
        "icon": "📉",
        "color": "#E76F51",
        "background": "#FFF1EC",
    },
    "Máquinas atendidas": {
        "icon": "❄️",
        "color": "#1F4E79",
        "background": "#EFF6FF",
    },
    "Técnicos envolvidos": {
        "icon": "👷",
        "color": "#1F4E79",
        "background": "#EFF6FF",
    },
    "Corretivas em garantia": {
        "icon": "✅",
        "color": "#2A9D8F",
        "background": "#EAF7F5",
    },
    "Corretivas fora da garantia": {
        "icon": "🚨",
        "color": "#C1121F",
        "background": "#FDECEC",
    },
    "Problema mais frequente": {
        "icon": "🔍",
        "color": "#6B7280",
        "background": "#F9FAFB",
    },
    "Peça mais trocada": {
        "icon": "🔧",
        "color": "#6B7280",
        "background": "#F9FAFB",
    },
}


def calculate_kpis(df):
    total = len(df)
    preventivas = len(df[df["Tipo"] == "Preventiva"])
    corretivas = len(df[df["Tipo"] == "Corretiva"])

    perc_prev = f"{(preventivas / total * 100):.1f}%" if total > 0 else "—"
    perc_corr = f"{(corretivas / total * 100):.1f}%" if total > 0 else "—"

    maquinas = df["Máquina"].nunique()
    tecnicos = df["Técnico"].nunique()

    df_corr = df[df["Tipo"] == "Corretiva"]

    em_garantia = len(df_corr[df_corr["Garantia"] == "Dentro"])
    fora_garantia = len(df_corr[df_corr["Garantia"] == "Fora"])

    prob_series = (
        df_corr["Problema"]
        .dropna()
        .astype(str)
        .str.split(";")
        .explode()
        .str.strip()
    )

    prob_series = prob_series[
        ~prob_series.str.lower().isin(["não informado", "nao informado"])
    ]

    prob_mais_freq = (
        prob_series.mode()[0]
        if not prob_series.empty
        else "—"
    )

    peca_series = (
        df["Peça"]
        .dropna()
        .astype(str)
        .str.split(";")
        .explode()
        .str.strip()
    )

    peca_series = peca_series[
        ~peca_series.str.lower().isin([
            "nenhuma",
            "não informado",
            "nao informado",
        ])
    ]

    peca_mais_trocada = (
        peca_series.mode()[0]
        if not peca_series.empty
        else "—"
    )

    return {
        "Total de tarefas": total,
        "Preventivas": preventivas,
        "Corretivas": corretivas,
        "% Preventivas": perc_prev,
        "% Corretivas": perc_corr,
        "Máquinas atendidas": maquinas,
        "Técnicos envolvidos": tecnicos,
        "Corretivas em garantia": em_garantia,
        "Corretivas fora da garantia": fora_garantia,
        "Problema mais frequente": prob_mais_freq,
        "Peça mais trocada": peca_mais_trocada,
    }


def _render_kpi_card(kpi_name, value):
    style = KPI_STYLES.get(
        kpi_name,
        {
            "icon": "📊",
            "color": "#1F4E79",
            "background": "#F9FAFB",
        },
    )

    icon = style["icon"]
    color = style["color"]
    background = style["background"]

    value_text = str(value)

    if len(value_text) > 28:
        value_text = value_text[:25] + "..."

    st.markdown(
        f"""
        <div style="
            background-color: {background};
            border: 1px solid #E5E7EB;
            border-left: 5px solid {color};
            border-radius: 12px;
            padding: 18px 20px;
            height: 130px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        ">
            <div style="
                font-size: 0.78rem;
                font-weight: 600;
                color: #6B7280;
                text-transform: uppercase;
                letter-spacing: 0.03em;
                margin-bottom: 8px;
            ">
                {icon} {kpi_name}
            </div>

            <div style="
                font-size: 1.65rem;
                font-weight: 700;
                color: {color};
                line-height: 1.15;
            ">
                {value_text}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_cards(selected_kpis, kpi_values):
    if not selected_kpis:
        return

    for i in range(0, len(selected_kpis), 4):
        kpi_group = selected_kpis[i:i + 4]
        cols = st.columns(len(kpi_group))

        for col, kpi_name in zip(cols, kpi_group):
            with col:
                value = kpi_values.get(kpi_name, "—")
                _render_kpi_card(kpi_name, value)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
