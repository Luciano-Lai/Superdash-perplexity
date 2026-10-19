import streamlit as st
from data_loader import load_and_normalize_data, norm
from filters import render_sidebar_filters, apply_filters, COLUMNS
from kpis import calculate_kpis, render_kpi_cards
from charts import render_evolution_chart, render_horizontal_ranking, render_donut_chart, render_cut_donut
from pdf_export import generate_pdf_report

st.set_page_config(page_title="Painel de Refrigeração", layout="wide")
st.markdown("""<style>
.block-container{max-width:1550px;padding-top:2rem;padding-bottom:3rem}
.kpi-card{background:var(--secondary-background-color,#fff);border:1px solid #DCE4EC;border-radius:12px;padding:18px;min-height:145px;box-sizing:border-box;margin-bottom:14px}
.kpi-label{font-size:.83rem;opacity:.8;margin-bottom:12px}
.kpi-value{font-weight:650;line-height:1.25;overflow-wrap:anywhere}
</style>""", unsafe_allow_html=True)
st.title("Painel de Refrigeração")
st.caption("Manutenções • equipamentos • operação")
try:
    df = load_and_normalize_data()
except Exception as error:
    st.error("Não foi possível carregar a base. O painel não exibirá números parciais.")
    with st.expander("Detalhes de diagnóstico"):
        st.write(str(error))
    st.stop()
if df.empty:
    st.info("A base não contém tarefas.")
    st.stop()
cut, valid, additional, spec = render_sidebar_filters(df)
if not valid or not additional:
    st.info("Selecione um período e pelo menos um filtro adicional na barra lateral.")
    st.stop()
if cut.empty:
    st.info("Nenhuma tarefa encontrada para os filtros selecionados.")
    st.stop()
start, end = spec["period"]
st.caption(f"Período: {start:%d/%m/%Y} a {end:%d/%m/%Y} • {len(cut)} tarefas no recorte")
active = [f"Tipo: {spec['Tipo']}"] if spec["Tipo"] != "Todas" else []
for column in COLUMNS:
    values = spec.get(column, [])
    if values:
        if column == "Máquina":
            labels = dict(zip(df["Máquina"], df["Seleção da máquina"]))
            values = [labels[v] for v in values]
        active.append(column + ": " + ", ".join(values))
st.caption(" | ".join(active))
values = calculate_kpis(cut)
with st.expander("Personalizar indicadores", expanded=False):
    chosen_kpis = st.multiselect("Indicadores exibidos", list(values), default=[], key="dash_kpis")
if chosen_kpis:
    st.subheader("Resumo do período")
    render_kpi_cards(chosen_kpis, values)
else:
    st.info("Selecione os indicadores em ‘Personalizar indicadores’.")

rankings = {
    "Tarefas por máquina": ("Rótulo da máquina", False),
    "Preventivas por máquina": ("Rótulo da máquina", "Preventiva"),
    "Corretivas por máquina": ("Rótulo da máquina", "Corretiva"),
    "Tarefas por técnico": ("Técnico", False),
    "Tarefas por cliente": ("Cliente", False),
    "Top problemas": ("Problema", "Corretiva"),
    "Top peças": ("Peça", "Corretiva"),
    "Top tarefas executadas": ("Tarefa", False),
}
options = ["Evolução no período"]
for name, (column, kind) in rankings.items():
    source = cut.loc[cut["Tipo"].eq(kind)] if kind else cut
    if not source.empty and source[column].astype(str).str.strip().ne("").any():
        options.append(name)
options.append("Participação do recorte no universo")
with st.expander("Visualizações e exportação", expanded=True):
    if not chosen_kpis:
        st.caption("Selecione ao menos um indicador para habilitar os gráficos.")
    selected = st.multiselect("Gráficos exibidos", options, default=[], key="dash_charts", disabled=not chosen_kpis)
    top_n = st.number_input("Top N padrão", min_value=1, max_value=100, value=10, key="dash_top_global")
    pdf_slot = st.container()
figures = {}
for name in selected if chosen_kpis else []:
    st.subheader(name)
    if name == "Evolução no período":
        c1, c2 = st.columns(2)
        gran = c1.selectbox("Agrupamento", ["Diária", "Semanal", "Mensal"], key="dash_gran")
        kind = c2.selectbox("Visual", ["Barras", "Linha", "Barras + linha acumulada"], key="dash_visual")
        fig = render_evolution_chart(cut, gran, kind, spec["period"])
        figures[name] = fig
        st.plotly_chart(fig, use_container_width=True)
    elif name == "Participação do recorte no universo":
        mode = st.selectbox("Universo de comparação", ["Todas as tarefas no período", "Mesmo tipo no período", "Personalizado"], key="dash_universe")
        universe_spec = {"period": spec["period"], "Tipo": "Todas"}
        if mode == "Mesmo tipo no período":
            universe_spec["Tipo"] = spec["Tipo"]
        elif mode == "Personalizado":
            keep = st.multiselect("Manter estes filtros ativos também no universo", [c for c in ["Tipo"]+COLUMNS if spec.get(c) and spec.get(c) != "Todas"], key="dash_universe_keep")
            for column in keep:
                universe_spec[column] = spec[column]
        universe = apply_filters(df, universe_spec)
        st.caption(f"Universo: {len(universe)} tarefas • recorte: {len(cut)} tarefas • mesmo período")
        fig = render_cut_donut(universe, cut)
        figures[name] = fig
        st.plotly_chart(fig, use_container_width=True)
    else:
        column, kind = rankings[name]
        source = cut.loc[cut["Tipo"].eq(kind)] if kind else cut
        with st.expander("Ajustes deste gráfico"):
            override = st.checkbox("Definir Top N individual", key="dash_override_"+name)
            n = st.number_input("Top N deste gráfico", min_value=1, max_value=100, value=10, key="dash_n_"+name) if override else top_n
            participation = st.checkbox("Exibir distribuição ao lado", key="dash_pair_"+name)
            others = st.checkbox("Agrupar restante em Outras", value=True, key="dash_others_"+name)
        fig = render_horizontal_ranking(source, column, name, n)
        figures[name] = fig
        if participation:
            left, right = st.columns([1.35, 1])
            left.plotly_chart(fig, use_container_width=True)
            donut = render_donut_chart(source, column, "Distribuição no recorte", n, others)
            right.plotly_chart(donut, use_container_width=True)
            figures[name+" — distribuição"] = donut
        else:
            st.plotly_chart(fig, use_container_width=True)

with pdf_slot:
    st.markdown("Exportação PDF")
    export_charts = st.multiselect("Gráficos para o PDF (seleção independente)", list(figures), key="dash_pdf_charts")
    # Associações explícitas, não inferidas do nome da coluna.
    associations = {
        "Evolução no período": {"Total de tarefas", "Preventivas", "Corretivas", "% Preventivas", "% Corretivas"},
        "Tarefas por máquina": {"Total de tarefas", "Máquinas atendidas"},
        "Preventivas por máquina": {"Preventivas", "% Preventivas"},
        "Corretivas por máquina": {"Corretivas", "% Corretivas"},
        "Tarefas por técnico": {"Total de tarefas", "Técnicos envolvidos"},
        "Tarefas por cliente": {"Total de tarefas", "Máquinas atendidas"},
        "Top problemas": {"Corretivas", "Problema mais frequente"},
        "Top peças": {"Corretivas", "Peça mais trocada"},
        "Top tarefas executadas": {"Total de tarefas"},
        "Participação do recorte no universo": {"Total de tarefas"},
    }
    allowed = set(values) if not export_charts else set().union(*(associations.get(n.replace(" — distribuição", ""), set()) for n in export_charts))
    export_kpis = st.multiselect("Indicadores para o PDF (sem gráficos, escolha livre)", [k for k in values if k in allowed], key="dash_pdf_kpis")
    per_page = st.selectbox("Gráficos por página", [1,2,3,4], key="dash_pdf_per_page")
    if st.button("Gerar PDF", disabled=not(export_charts or export_kpis)):
        try:
            data = generate_pdf_report(values, export_kpis, {n: figures[n] for n in export_charts}, per_page)
            st.download_button("Baixar PDF", data, "painel_refrigeracao.pdf", "application/pdf")
        except Exception as error:
            st.error("Não foi possível gerar o PDF. Para gráficos, confira Kaleido e Chromium.")
            st.code(str(error))

corr = cut.loc[cut["Tipo"].eq("Corretiva")]
missing_problem = int(corr["Problema"].map(norm).isin(["", "nao informado"]).sum())
missing_warranty = int(corr["Data Garantia"].isna().sum())
with st.expander("Qualidade dos dados e critério de garantia"):
    st.write(f"Corretivas sem problema válido: {missing_problem} • sem data de garantia: {missing_warranty}")
    st.warning("Garantia nesta versão: situação atual da data limite informada. Isso NÃO confirma se a chamada foi coberta pela garantia na data da ocorrência. A regra histórica precisa ser validada.")
with st.expander("Detalhamento dos registros", expanded=False):
    size = st.selectbox("Registros por página", [15,25,50,100], key="dash_page_size")
    ordered = cut.sort_values("Data da tarefa", ascending=False)
    pages = max(1, (len(ordered)+size-1)//size)
    page = st.selectbox("Página", list(range(1, pages+1)), key="dash_page")
    st.caption(f"{len(ordered)} registros • página {page} de {pages}")
    st.dataframe(ordered.iloc[(page-1)*size:page*size], hide_index=True, use_container_width=True)
