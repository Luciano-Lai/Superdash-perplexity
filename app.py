import streamlit as st
from data_loader import load_and_normalize_data
from filters import render_sidebar_filters
from kpis import calculate_kpis, render_kpi_cards
from charts import render_evolution_chart, render_horizontal_ranking, render_donut_chart
from pdf_export import generate_pdf_report

st.set_page_config(page_title="Painel de Refrigeração", layout="wide")

st.title("❄️ Painel de Acompanhamento de Refrigeração")

# 1. Carrega dados do Google Sheets
df_raw = load_and_normalize_data()

# 2. Barra de Filtros Lateral
df_filtered, is_date_valid, has_additional_filter = render_sidebar_filters(df_raw)

# 3. Estado Inicial / Mensagens de Alerta
if not is_date_valid:
    st.info("Selecione o período e os filtros para visualizar os indicadores.")
    st.stop()

if not has_additional_filter:
    st.warning("Aplique pelo menos um filtro adicional para visualizar os dados.")
    st.stop()

if df_filtered.empty:
    st.warning("Nenhum registro encontrado para os filtros selecionados.")
    st.stop()

# 4. Cálculo de KPIs
kpi_values = calculate_kpis(df_filtered)

st.subheader("1. Indicadores Chave (KPIs)")
all_kpi_names = list(kpi_values.keys())
selected_kpis = st.multiselect("Selecione os KPIs que deseja visualizar:", options=all_kpi_names, default=[])

if not selected_kpis:
    st.info("Selecione pelo menos um KPI para visualizar os cartões.")
else:
    render_kpi_cards(selected_kpis, kpi_values)

# 5. Submenu de Gráficos
if selected_kpis:
    st.markdown("---")
    st.subheader("2. Submenu de Gráficos")

    top_n_global = st.number_input("Top N Padrão Global", min_value=1, max_value=50, value=10)

    available_charts = [
        "Evolução no período",
        "Tarefas por máquina",
        "Corretivas por máquina",
        "Tarefas por técnico",
        "Top problemas",
        "Top peças",
        "Rosca - Universo de análise"
    ]

    selected_charts = st.multiselect("Selecione os gráficos a exibir:", options=available_charts, default=[])

    if not selected_charts:
        st.info("Selecione pelo menos um gráfico no submenu.")
    else:
        st.markdown("---")
        st.subheader("3. Área de Visualização")

        if "Evolução no período" in selected_charts:
            c1, c2 = st.columns([1, 1])
            with c1:
                gran = st.selectbox("Granularidade", ["Diária", "Semanal", "Mensal"])
            with c2:
                ctype = st.selectbox("Tipo de Gráfico", ["Barras", "Linha", "Barras + linha acumulada"])
            fig_evo = render_evolution_chart(df_filtered, granularity=gran, chart_type=ctype)
            st.plotly_chart(fig_evo, use_container_width=True)

        if "Tarefas por máquina" in selected_charts:
            fig_maq = render_horizontal_ranking(df_filtered, "Máquina", "Tarefas por Máquina", top_n=top_n_global)
            st.plotly_chart(fig_maq, use_container_width=True)

        if "Top problemas" in selected_charts:
            df_corr = df_filtered[df_filtered["Tipo"] == "Corretiva"]
            if df_corr.empty:
                st.info("Não houve problemas registrados no período selecionado.")
            else:
                fig_prob = render_horizontal_ranking(df_corr, "Problema", "Top Problemas Relatados", top_n=top_n_global)
                st.plotly_chart(fig_prob, use_container_width=True)

        if "Rosca - Universo de análise" in selected_charts:
            fig_rosca = render_donut_chart(df_filtered, "Máquina", "Participação no Total de Tarefas", top_n=top_n_global)
            st.plotly_chart(fig_rosca, use_container_width=True)

        # Exportação em PDF
        st.markdown("---")
        st.subheader("4. Exportação")
        if st.button("📄 Exportar Relatório em PDF"):
            pdf_bytes = generate_pdf_report(kpi_values, selected_kpis)
            st.download_button(
                label="⬇️ Baixar PDF",
                data=pdf_bytes,
                file_name="relatorio_refrigeracao.pdf",
                mime="application/pdf"
            )

# 6. Tabela de Detalhamento
st.markdown("---")
with st.expander("📋 Tabela de Detalhamento de Registros (Minimizada)"):
    page_size = st.selectbox("Registros por página", [15, 25, 50, 100], index=0)
    st.dataframe(df_filtered.sort_values(by="Data da tarefa", ascending=False).head(page_size), use_container_width=True)
