import hashlib
import math
import unicodedata

import streamlit as st

from charts import (
    render_evolution_chart, render_horizontal_ranking,
    render_donut_chart, render_cut_donut,
)
from filters import apply_filters, COLUMNS
from kpis import calculate_kpis, render_kpi_cards
from pdf_export import generate_pdf_report

PAGE_INFO = {
    "monitoramento": ("Monitoramento", "Visão consolidada da operação no recorte selecionado."),
    "analise_tarefas": ("Análise de tarefas", "Volume, composição e serviços executados."),
    "maquinas": ("Máquinas", "Distribuição de atendimentos e ocorrências por equipamento."),
    "corretivas": ("Corretivas", "Problemas, peças e serviços de manutenção corretiva."),
    "clientes_regioes": ("Clientes e regiões", "Distribuição dos atendimentos por cliente e localização."),
}

RANKINGS = {
    "Tarefas por máquina": ("Rótulo da máquina", None),
    "Preventivas por máquina": ("Rótulo da máquina", "Preventiva"),
    "Corretivas por máquina": ("Rótulo da máquina", "Corretiva"),
    "Tarefas por técnico": ("Técnico", None),
    "Tarefas por cliente": ("Cliente", None),
    "Tarefas por cidade": ("Cidade", None),
    "Tarefas por região": ("Região", None),
    "Tarefas por estado": ("Estado", None),
    "Top problemas": ("Problema", "Corretiva"),
    "Top peças": ("Peça", "Corretiva"),
    "Top tarefas executadas": ("Tarefa", None),
}
PAGE_RANKINGS = {
    "monitoramento": list(RANKINGS),
    "analise_tarefas": ["Top tarefas executadas", "Tarefas por máquina", "Tarefas por técnico", "Tarefas por cliente"],
    "maquinas": ["Tarefas por máquina", "Preventivas por máquina", "Corretivas por máquina", "Top problemas", "Top peças"],
    "corretivas": ["Corretivas por máquina", "Top problemas", "Top peças", "Top tarefas executadas"],
    "clientes_regioes": ["Tarefas por cliente", "Tarefas por cidade", "Tarefas por região", "Tarefas por estado", "Tarefas por máquina"],
}
ASSOCIATIONS = {
    "Evolução no período": {"Total de tarefas", "Preventivas", "Corretivas", "% Preventivas", "% Corretivas"},
    "Tarefas por máquina": {"Total de tarefas", "Máquinas atendidas"},
    "Preventivas por máquina": {"Preventivas", "% Preventivas"},
    "Corretivas por máquina": {"Corretivas", "% Corretivas"},
    "Tarefas por técnico": {"Total de tarefas", "Técnicos envolvidos"},
    "Top problemas": {"Corretivas", "Problema mais frequente"},
    "Top peças": {"Corretivas", "Peça mais trocada"},
}


def apply_theme():
    st.markdown("""<style>
.block-container{max-width:1550px;padding-top:2rem;padding-bottom:3rem}
.kpi-card{background:var(--secondary-background-color,#fff);border:1px solid #DCE4EC;border-radius:12px;padding:18px;min-height:145px;box-sizing:border-box;margin-bottom:14px}
.kpi-label{font-size:.83rem;opacity:.8;margin-bottom:12px}
.kpi-value{font-weight:650;line-height:1.25;overflow-wrap:anywhere}
</style>""", unsafe_allow_html=True)


def persist_widget(kind, label, key, **kwargs):
    saved = key + "_saved"
    if saved in st.session_state:
        value = st.session_state[saved]
        options = kwargs.get("options")
        if options is not None:
            if kind == "multiselect":
                value = [v for v in value if v in options]
            elif value not in options:
                value = options[0]
        st.session_state[key] = value
        kwargs.pop("default", None)
        kwargs.pop("value", None)
    def save():
        st.session_state[saved] = st.session_state[key]
    value = getattr(st, kind)(label, key=key, on_change=save, **kwargs)
    st.session_state[saved] = value
    return value


def normalize_header(value):
    text = unicodedata.normalize("NFKD", str(value).strip().lower())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def detail_columns(columns):
    markers = {"codigo do patrimonio", "codigo de patrimonio", "codigo patrimonio", "cod. patrimonio", "cod patrimonio"}
    cutoff = next((i for i, col in enumerate(columns) if normalize_header(col) in markers), None)
    if cutoff is not None:
        keep = list(columns[:cutoff])
        # Não mostrar campos auxiliares criados só para navegação e gráficos.
        keep = [c for c in keep if c not in {"Rótulo da máquina", "Seleção da máquina"}]
    else:
        preferred = ["Data da tarefa", "Nome da máquina", "Máquina", "Tipo", "Técnico", "Cliente", "Cidade", "Região", "Estado", "Problema", "Tarefa", "Peça", "Observações"]
        keep = [c for c in preferred if c in columns]
    if "Garantia" in columns and "Garantia" not in keep:
        keep.append("Garantia")
    return keep, cutoff is not None


def render_detail(df, page_id, signature):
    with st.expander("Detalhamento dos registros", expanded=False):
        shown, found = detail_columns(list(df.columns))
        if not found:
            st.caption("Cabeçalho de patrimônio não localizado: exibindo apenas as colunas essenciais, sem campos adicionais do cadastro.")
        prefix = "dash_" + page_id + "_detail"
        size = st.selectbox("Registros por página", [15,25,50,100], key=prefix+"_size")
        marker = signature + ":" + str(size)
        if st.session_state.get(prefix+"_signature") != marker:
            st.session_state[prefix+"_page"] = 1
            st.session_state[prefix+"_signature"] = marker
        pages = max(1, math.ceil(len(df)/size))
        current = st.number_input("Página", min_value=1, max_value=pages, step=1, key=prefix+"_page")
        ordered = df.sort_values("Data da tarefa", ascending=False)
        st.caption(f"{len(df)} registros • página {current} de {pages}")
        st.dataframe(ordered.iloc[(current-1)*size:current*size][shown], hide_index=True, use_container_width=True)


def render_export(figures, associations, values, page_id):
    p = "dash_" + page_id + "_pdf_"
    charts = persist_widget("multiselect", "Gráficos para o PDF", p+"charts", options=list(figures), default=[])
    allowed = set(values) if not charts else set().union(*(associations[n] for n in charts))
    kpis = persist_widget("multiselect", "Indicadores para o PDF", p+"kpis", options=[k for k in values if k in allowed], default=[])
    st.caption("Sem gráficos selecionados, é possível exportar apenas indicadores. Com gráficos, aparecem somente indicadores associados.")
    count = persist_widget("selectbox", "Gráficos por página", p+"count", options=[1,2,3,4])
    if st.button("Gerar PDF", key=p+"generate", disabled=not(charts or kpis)):
        try:
            pdf = generate_pdf_report(values, kpis, {n:figures[n] for n in charts}, count)
            st.download_button("Baixar PDF", pdf, "painel_"+page_id+".pdf", "application/pdf", key=p+"download")
        except Exception as error:
            st.error("A exportação não foi concluída. Confira as dependências do PDF no servidor.")
            st.code(str(error))


def render_page(page_id):
    title, subtitle = PAGE_INFO[page_id]
    st.title(title)
    st.caption(subtitle)
    ctx = st.session_state["_page_context"]
    if not ctx["valid"] or not ctx["additional"]:
        st.info("Selecione o período e pelo menos um filtro adicional para visualizar os indicadores.")
        return
    df = ctx["cut"].copy()
    if page_id == "corretivas":
        st.caption("Escopo desta página: somente corretivas, respeitando os filtros comuns.")
        df = df.loc[df["Tipo"].eq("Corretiva")]
    if df.empty:
        st.info("Nenhum registro encontrado para os filtros selecionados nesta página.")
        return
    spec = ctx["spec"]
    start, end = spec["period"]
    st.caption(f"{start:%d/%m/%Y} a {end:%d/%m/%Y} • {len(df)} tarefas no recorte")
    parts = []
    for column in ["Tipo"] + COLUMNS:
        selection = spec.get(column)
        if not selection or selection == "Todas":
            continue
        if column == "Máquina":
            labels = dict(zip(ctx["raw"]["Máquina"], ctx["raw"]["Seleção da máquina"]))
            selection = [labels.get(v,v) for v in selection]
        parts.append(column + ": " + (selection if isinstance(selection,str) else ", ".join(selection)))
    st.caption(" | ".join(parts))
    prefix = "dash_" + page_id + "_"
    values = calculate_kpis(df)
    with st.expander("Personalizar indicadores", expanded=False):
        selected_kpis = persist_widget("multiselect", "Indicadores exibidos", prefix+"kpis", options=list(values), default=[])
    if selected_kpis:
        st.subheader("Resumo do período")
        render_kpi_cards(selected_kpis, values)
    else:
        st.info("Selecione ao menos um indicador em Personalizar indicadores.")
    available = ["Evolução no período"]
    for name in PAGE_RANKINGS[page_id]:
        column, kind = RANKINGS[name]
        source = df.loc[df["Tipo"].eq(kind)] if kind else df
        if column in source and source[column].fillna("").astype(str).str.strip().ne("").any():
            available.append(name)
    available.append("Participação do recorte no universo")
    with st.expander("Visualizações e exportação", expanded=True):
        selected = persist_widget("multiselect", "Gráficos exibidos", prefix+"charts", options=available, default=[], disabled=not selected_kpis)
        c1,c2 = st.columns(2)
        with c1:
            if st.button("Selecionar tudo", key=prefix+"select_all", disabled=not selected_kpis):
                st.session_state[prefix+"charts_saved"] = available
                st.rerun()
        with c2:
            if st.button("Limpar seleção de gráficos", key=prefix+"clear_charts"):
                st.session_state[prefix+"charts_saved"] = []
                st.rerun()
        # O mesmo widget é executado pela página ativa; cópia salva evita perder o valor ao navegar.
        top_n = persist_widget("number_input", "Top N padrão global", "dash_global_top", min_value=1, max_value=100, value=10)
        export_slot = st.container()
    figures, assoc = {}, {}
    for name in selected if selected_kpis else []:
        st.subheader(name)
        key = prefix + hashlib.sha1(name.encode()).hexdigest()[:10]
        if name == "Evolução no período":
            left,right = st.columns(2)
            with left:
                gran = persist_widget("selectbox", "Agrupamento", key+"gran", options=["Diá
