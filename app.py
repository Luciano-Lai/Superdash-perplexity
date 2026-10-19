import streamlit as st
import pandas as pd

from data_loader import load_and_normalize_data
from filters import render_sidebar_filters
from kpis import calculate_kpis, render_kpi_cards
from charts import (
    render_evolution_chart,
    render_horizontal_ranking,
    render_donut_chart,
)
from pdf_export import generate_pdf_report

# ------------------------------------------------------------------
# Configuração inicial
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Painel de Refrigeração",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 2rem;
            max-width: 1650px;
        }

        h1 {
            font-size: 1.55rem !important;
            font-weight: 700 !important;
            color: #111827 !important;
            margin-bottom: 0.15rem !important;
        }

        .app-subtitle {
            color: #6B7280;
            font-size: 0.92rem;
            margin-bottom: 1.5rem;
        }

        .section-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: #111827;
            margin: 1.6rem 0 0.8rem 0;
        }

        .filter-chip {
            display: inline-block;
            background-color: #EFF6FF;
            color: #1F4E79;
            border: 1px solid #BFDBFE;
            border-radius: 999px;
            padding: 4px 12px;
            font-size: 0.78rem;
            font-weight: 600;
            margin-right: 6px;
            margin-bottom: 6px;
        }

        div[data-testid="stExpander"] {
            border: 1px solid #E5E7EB;
            border-radius: 12px;
            background-color: #FFFFFF;
        }

        div[data-testid="stPlotlyChart"] {
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
            padding: 10px;
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid #E5E7EB;
            border-radius: 10px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------
# Cabeçalho
# ------------------------------------------------------------------
st.title("Painel de Refrigeração")
st.markdown(
    "<div class='app-subtitle'>Acompanhamento de tarefas, preventivas, corretivas, problemas, peças e garantias</div>",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------
# Dados e filtros
# ------------------------------------------------------------------
df_raw = load_and_normalize_data()
df_filtered, is_date_valid, has_additional_filter = render_sidebar_filters(df_raw)

if not is_date_valid:
    st.info("Selecione o período e os filtros para visualizar os indicadores.")
    st.stop()

if not has_additional_filter:
    st.warning("Aplique pelo menos um filtro adicional para visualizar os dados.")
    st.stop()

if df_filtered.empty:
    st.warning("Nenhum registro encontrado para os filtros selecionados.")
    st.stop()

# ------------------------------------------------------------------
# Resumo executivo
# ------------------------------------------------------------------
kpi_values = calculate_kpis(df_filtered)

st.markdown("<div class='section-title'>Resumo executivo</div>", unsafe_allow_html=True)

default_kpis = [
    "Total de tarefas",
    "Corretivas",
    "% Corretivas",
    "Corretivas fora da garantia",
]

available_kpis = list(kpi_values.keys())

selected_kpis = st.multiselect(
    "Indicadores exibidos",
    options=available_kpis,
    default=[kpi for kpi in default_kpis if kpi in available_kpis],
    label_visibility="collapsed",
)

if not selected_kpis:
    st.info("Selecione pelo menos um indicador para visualizar os cartões.")
    st.stop()

render_kpi_cards(selected_kpis, kpi_values)

# ------------------------------------------------------------------
# Configuração de visualizações
# ------------------------------------------------------------------
available_charts = [
    "Evolução no período",
    "Tarefas por máquina",
    "Corretivas por máquina",
    "Tarefas por técnico",
    "Top problemas",
    "Top peças",
    "Rosca — Universo de análise",
]

with st.expander("⚙️ Configurar visualizações e exportação", expanded=False):
    config_col1, config_col2, config_col3 = st.columns([2.2, 0.8, 1])

    with config_col1:
        selected_charts = st.multiselect(
            "Gráficos exibidos",
            options=available_charts,
            default=["Evolução no período"],
            label_visibility="collapsed",
        )

    with config_col2:
        top_n_global = st.number_input(
            "Top N padrão",
            min_value=1,
            max_value=50,
            value=10,
            label_visibility="collapsed",
        )

    with config_col3:
        pdf_bytes = generate_pdf_report(kpi_values, selected_kpis)

        st.download_button(
            label="📄 Exportar PDF",
            data=pdf_bytes,
            file_name="relatorio_refrigeracao.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

if not selected_charts:
    st.info("Selecione pelo menos um gráfico para visualizar as análises.")
    st.stop()

# ------------------------------------------------------------------
# Evolução no período
# ------------------------------------------------------------------
if "Evolução no período" in selected_charts:
    st.markdown(
        "<div class='section-title'>Evolução no período</div>",
        unsafe_allow_html=True,
    )

    evolution_col1, evolution_col2 = st.columns([1, 1])

    with evolution_col1:
        granularity = st.selectbox(
            "Granularidade",
            ["Diária", "Semanal", "Mensal"],
            label_visibility="collapsed",
        )

    with evolution_col2:
        chart_type = st.selectbox(
            "Tipo de visualização",
            ["Barras", "Linha", "Barras + linha acumulada"],
            label_visibility="collapsed",
        )

    fig_evolution = render_evolution_chart(
        df_filtered,
        granularity=granularity,
        chart_type=chart_type,
    )

    st.plotly_chart(fig_evolution, use_container_width=True)

# ------------------------------------------------------------------
# Rankings
# ------------------------------------------------------------------
ranking_chart_map = {
    "Tarefas por máquina": {
        "column": "Máquina",
        "title": "Tarefas por máquina",
        "corrective_only": False,
    },
    "Corretivas por máquina": {
        "column": "Máquina",
        "title": "Corretivas por máquina",
        "corrective_only": True,
    },
    "Tarefas por técnico": {
        "column": "Técnico",
        "title": "Tarefas por técnico",
        "corrective_only": False,
    },
    "Top problemas": {
        "column": "Problema",
        "title": "Top problemas relatados",
        "corrective_only": True,
    },
    "Top peças": {
        "column": "Peça",
        "title": "Top peças trocadas",
        "corrective_only": True,
    },
}

selected_rankings = [
    chart for chart in selected_charts
    if chart in ranking_chart_map
]

if selected_rankings:
    st.markdown(
        "<div class='section-title'>Análises por categoria</div>",
        unsafe_allow_html=True,
    )

    for i in range(0, len(selected_rankings), 2):
        charts_pair = selected_rankings[i:i + 2]
        ranking_cols = st.columns(len(charts_pair))

        for col, chart_name in zip(ranking_cols, charts_pair):
            config = ranking_chart_map[chart_name]
            df_chart = df_filtered.copy()

            if config["corrective_only"]:
                df_chart = df_chart[df_chart["Tipo"] == "Corretiva"]

            with col:
                if df_chart.empty:
                    st.info("Não há dados suficientes para este gráfico.")
                    continue

                fig_ranking = render_horizontal_ranking(
                    df_chart,
                    config["column"],
                    config["title"],
                    top_n=top_n_global,
                )

                st.plotly_chart(fig_ranking, use_container_width=True)

# ------------------------------------------------------------------
# Rosca — universo de análise
# ------------------------------------------------------------------
if "Rosca — Universo de análise" in selected_charts:
    st.markdown(
        "<div class='section-title'>Participação no total</div>",
        unsafe_allow_html=True,
    )

    fig_donut = render_donut_chart(
        df_filtered,
        "Máquina",
        "Participação no total de tarefas",
        top_n=top_n_global,
    )

    st.plotly_chart(fig_donut, use_container_width=True)

# ------------------------------------------------------------------
# Detalhamento
# ------------------------------------------------------------------
with st.expander("📋 Detalhamento dos registros"):
    page_size = st.selectbox(
        "Registros por página",
        [15, 25, 50, 100],
        index=0,
        label_visibility="collapsed",
    )

    st.dataframe(
        df_filtered.sort_values(
            by="Data da tarefa",
            ascending=False,
        ).head(page_size),
        use_container_width=True,
        hide_index=True,
    )
