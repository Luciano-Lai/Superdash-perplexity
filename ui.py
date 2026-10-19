import hashlib
import math
import unicodedata

import streamlit as st

from charts import (
    render_evolution_chart,
    render_horizontal_ranking,
    render_donut_chart,
    render_cut_donut,
)
from filters import apply_filters, COLUMNS
from kpis import calculate_kpis, render_kpi_cards
from pdf_export import generate_pdf_report


PAGE_INFO = {
    "monitoramento": (
        "Monitoramento",
        "Visão consolidada da operação no recorte selecionado.",
    ),
    "analise_tarefas": (
        "Análise de tarefas",
        "Volume, composição e serviços executados.",
    ),
    "maquinas": (
        "Máquinas",
        "Distribuição de atendimentos e ocorrências por equipamento.",
    ),
    "corretivas": (
        "Corretivas",
        "Problemas, peças e serviços de manutenção corretiva.",
    ),
    "clientes_regioes": (
        "Clientes e regiões",
        "Distribuição dos atendimentos por cliente e localização.",
    ),
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
    "analise_tarefas": [
        "Top tarefas executadas",
        "Tarefas por máquina",
        "Tarefas por técnico",
        "Tarefas por cliente",
    ],
    "maquinas": [
        "Tarefas por máquina",
        "Preventivas por máquina",
        "Corretivas por máquina",
        "Top problemas",
        "Top peças",
    ],
    "corretivas": [
        "Corretivas por máquina",
        "Top problemas",
        "Top peças",
        "Top tarefas executadas",
    ],
    "clientes_regioes": [
        "Tarefas por cliente",
        "Tarefas por cidade",
        "Tarefas por região",
        "Tarefas por estado",
        "Tarefas por máquina",
    ],
}


ASSOCIATIONS = {
    "Evolução no período": {
        "Total de tarefas",
        "Preventivas",
        "Corretivas",
        "% Preventivas",
        "% Corretivas",
    },
    "Tarefas por máquina": {
        "Total de tarefas",
        "Máquinas atendidas",
    },
    "Preventivas por máquina": {
        "Preventivas",
        "% Preventivas",
    },
    "Corretivas por máquina": {
        "Corretivas",
        "% Corretivas",
    },
    "Tarefas por técnico": {
        "Total de tarefas",
        "Técnicos envolvidos",
    },
    "Tarefas por cliente": {
        "Total de tarefas",
        "Máquinas atendidas",
    },
    "Tarefas por cidade": {
        "Total de tarefas",
        "Máquinas atendidas",
    },
    "Tarefas por região": {
        "Total de tarefas",
        "Máquinas atendidas",
    },
    "Tarefas por estado": {
        "Total de tarefas",
        "Máquinas atendidas",
    },
    "Top problemas": {
        "Corretivas",
        "Problema mais frequente",
    },
    "Top peças": {
        "Corretivas",
        "Peça mais trocada",
    },
    "Top tarefas executadas": {
        "Total de tarefas",
    },
    "Participação do recorte no universo": {
        "Total de tarefas",
    },
}


def apply_theme():
    css = """
    <style>
    .block-container {
        max-width: 1550px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    .kpi-card {
        background: var(--secondary-background-color, #FFFFFF);
        border: 1px solid #DCE4EC;
        border-radius: 12px;
        padding: 18px;
        min-height: 145px;
        box-sizing: border-box;
        margin-bottom: 14px;
    }

    .kpi-label {
        font-size: 0.83rem;
        opacity: 0.8;
        margin-bottom: 12px;
    }

    .kpi-value {
        font-weight: 650;
        line-height: 1.25;
        overflow-wrap: anywhere;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def persist_widget(kind, label, key, **kwargs):
    saved_key = key + "_saved"
    options = kwargs.get("options")

    if saved_key in st.session_state:
        value = st.session_state[saved_key]

        if options is not None:
            options = list(options)

            if kind == "multiselect":
                value = [
                    item
                    for item in value
                    if item in options
                ]
            elif options and value not in options:
                value = options[0]

        st.session_state[key] = value
        kwargs.pop("default", None)
        kwargs.pop("value", None)

    def save_value():
        st.session_state[saved_key] = st.session_state[key]

    widget = getattr(st, kind)

    value = widget(
        label,
        key=key,
        on_change=save_value,
        **kwargs,
    )

    st.session_state[saved_key] = value
    return value


def normalize_header(value):
    text = unicodedata.normalize(
        "NFKD",
        str(value).strip().lower(),
    )

    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )

    return " ".join(text.split())


def detail_columns(columns):
    markers = {
        "codigo do patrimonio",
        "codigo de patrimonio",
        "codigo patrimonio",
        "cod. patrimonio",
        "cod patrimonio",
    }

    cutoff = next(
        (
            index
            for index, column in enumerate(columns)
            if normalize_header(column) in markers
        ),
        None,
    )

    if cutoff is not None:
        selected = list(columns[:cutoff])

        selected = [
            column
            for column in selected
            if column not in {
                "Rótulo da máquina",
                "Seleção da máquina",
            }
        ]
    else:
        preferred = [
            "Data da tarefa",
            "Nome da máquina",
            "Máquina",
            "Tipo",
            "Técnico",
            "Cliente",
            "Cidade",
            "Região",
            "Estado",
            "Problema",
            "Tarefa",
            "Peça",
            "Observações",
        ]

        selected = [
            column
            for column in preferred
            if column in columns
        ]

    if "Garantia" in columns and "Garantia" not in selected:
        selected.append("Garantia")

    return selected, cutoff is not None


def render_detail(df, page_id, signature):
    with st.expander(
        "Detalhamento dos registros",
        expanded=False,
    ):
        columns, marker_found = detail_columns(
            list(df.columns)
        )

        if not marker_found:
            st.caption(
                "Cabeçalho de patrimônio não localizado. "
                "Exibindo somente as colunas essenciais, "
                "sem campos adicionais do cadastro."
            )

        prefix = "dash_" + page_id + "_detail"

        page_size = st.selectbox(
            "Registros por página",
            [15, 25, 50, 100],
            key=prefix + "_size",
        )

        pagination_signature = (
            signature + ":" + str(page_size)
        )

        if (
            st.session_state.get(prefix + "_signature")
            != pagination_signature
        ):
            st.session_state[prefix + "_page"] = 1
            st.session_state[prefix + "_signature"] = (
                pagination_signature
            )

        total_pages = max(
            1,
            math.ceil(len(df) / page_size),
        )

        page_key = prefix + "_page"

        stored_page = st.session_state.get(page_key, 1)

        if stored_page < 1 or stored_page > total_pages:
            st.session_state[page_key] = 1

        current_page = st.number_input(
            "Página",
            min_value=1,
            max_value=total_pages,
            step=1,
            key=page_key,
        )

        current_page = int(current_page)

        ordered = df.sort_values(
            "Data da tarefa",
            ascending=False,
        )

        first = (current_page - 1) * page_size
        last = current_page * page_size

        st.caption(
            f"{len(df)} registros • "
            f"página {current_page} de {total_pages}"
        )

        st.dataframe(
            ordered.iloc[first:last][columns],
            hide_index=True,
            use_container_width=True,
        )


def render_export(
    figures,
    associations,
    values,
    page_id,
):
    prefix = "dash_" + page_id + "_pdf_"

    selected_charts = persist_widget(
        "multiselect",
        "Gráficos para o PDF",
        prefix + "charts",
        options=list(figures),
        default=[],
    )

    if selected_charts:
        allowed_kpis = set()

        for name in selected_charts:
            allowed_kpis.update(
                associations.get(name, set())
            )
    else:
        allowed_kpis = set(values)

    selected_kpis = persist_widget(
        "multiselect",
        "Indicadores para o PDF",
        prefix + "kpis",
        options=[
            name
            for name in values
            if name in allowed_kpis
        ],
        default=[],
    )

    st.caption(
        "Sem gráficos selecionados, você pode exportar "
        "apenas indicadores. Com gráficos selecionados, "
        "aparecem somente os indicadores associados."
    )

    charts_per_page = persist_widget(
        "selectbox",
        "Gráficos por página",
        prefix + "count",
        options=[1, 2, 3, 4],
    )

    generate = st.button(
        "Gerar PDF",
        key=prefix + "generate",
        disabled=not (
            selected_charts or selected_kpis
        ),
    )

    if generate:
        try:
            chosen_figures = {
                name: figures[name]
                for name in selected_charts
            }

            pdf = generate_pdf_report(
                values,
                selected_kpis,
                chosen_figures,
                charts_per_page,
            )

            st.download_button(
                label="Baixar PDF",
                data=pdf,
                file_name="painel_" + page_id + ".pdf",
                mime="application/pdf",
                key=prefix + "download",
            )

        except Exception as error:
            st.error(
                "A exportação não foi concluída. "
                "Confira as dependências do PDF no servidor."
            )
            st.code(str(error))


def render_filter_summary(context):
    spec = context["spec"]
    parts = []

    for column in ["Tipo"] + list(COLUMNS):
        selection = spec.get(column)

        if not selection:
            continue

        if isinstance(selection, str):
            if selection == "Todas":
                continue
            display = selection

        else:
            if column == "Máquina":
                labels = dict(
                    zip(
                        context["raw"]["Máquina"],
                        context["raw"]["Seleção da máquina"],
                    )
                )

                selection = [
                    labels.get(value, value)
                    for value in selection
                ]

            display = ", ".join(
                str(value)
                for value in selection
            )

        parts.append(column + ": " + display)

    if parts:
        st.caption(" | ".join(parts))


def available_chart_names(df, page_id):
    available = ["Evolução no período"]

    for name in PAGE_RANKINGS[page_id]:
        column, maintenance_type = RANKINGS[name]

        if maintenance_type:
            source = df.loc[
                df["Tipo"].eq(maintenance_type)
            ]
        else:
            source = df

        if column not in source.columns:
            continue

        has_values = (
            source[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .ne("")
            .any()
        )

        if has_values:
            available.append(name)

    available.append(
        "Participação do recorte no universo"
    )

    return available


def render_evolution(df, spec, key):
    left, right = st.columns(2)

    with left:
        granularity = persist_widget(
            "selectbox",
            "Agrupamento",
            key + "_gran",
            options=[
                "Diária",
                "Semanal",
                "Mensal",
            ],
        )

    with right:
        chart_type = persist_widget(
            "selectbox",
            "Visual",
            key + "_visual",
            options=[
                "Barras",
                "Linha",
                "Barras + linha acumulada",
            ],
        )

    return render_evolution_chart(
        df,
        granularity,
        chart_type,
        spec["period"],
    )


def render_universe(df, context, page_id, key):
    spec = context["spec"]

    mode = persist_widget(
        "selectbox",
        "Universo de comparação",
        key + "_universe",
        options=[
            "Todas as tarefas no período",
            "Mesmo tipo no período",
            "Personalizado",
        ],
    )

    universe_spec = {
        "period": spec["period"],
        "Tipo": "Todas",
    }

    if mode == "Mesmo tipo no período":
        if page_id == "corretivas":
            universe_spec["Tipo"] = "Corretiva"
        else:
            universe_spec["Tipo"] = spec["Tipo"]

    elif mode == "Personalizado":
        candidates = []

        for column in ["Tipo"] + list(COLUMNS):
            value = spec.get(column)

            if not value:
                continue

            if isinstance(value, str) and value == "Todas":
                continue

            candidates.append(column)

        keep = persist_widget(
            "multiselect",
            "Manter filtros ativos no universo",
            key + "_keep",
            options=candidates,
            default=[],
        )

        for column in keep:
            universe_spec[column] = spec[column]

    universe = apply_filters(
        context["raw"],
        universe_spec,
    )

    st.caption(
        f"Universo: {len(universe)} tarefas • "
        f"recorte: {len(df)} tarefas • mesmo período."
    )

    if page_id == "corretivas":
        st.caption(
            "Nesta página, o recorte contém somente corretivas. "
            "O universo segue a opção escolhida acima."
        )

    return render_cut_donut(
        universe,
        df,
    )


def render_ranking_block(
    df,
    name,
    key,
    top_n_global,
):
    column, maintenance_type = RANKINGS[name]

    if maintenance_type:
        source = df.loc[
            df["Tipo"].eq(maintenance_type)
        ]
    else:
        source = df

    with st.expander("Ajustes deste gráfico"):
        override = persist_widget(
            "checkbox",
            "Definir Top N individual",
            key + "_override",
            value=False,
        )

        if override:
            top_n = persist_widget(
                "number_input",
                "Top N individual",
                key + "_n",
                min_value=1,
                max_value=100,
                value=10,
            )
        else:
            top_n = top_n_global

        show_distribution = persist_widget(
            "checkbox",
            "Exibir distribuição ao lado",
            key + "_pair",
            value=False,
        )

        show_others = persist_widget(
            "checkbox",
            "Agrupar restante em Outras",
            key + "_others",
            value=True,
        )

    figure = render_horizontal_ranking(
        source,
        column,
        name,
        top_n,
    )

    result = {name: figure}

    if show_distribution:
        left, right = st.columns([1.35, 1])

        left.plotly_chart(
            figure,
            use_container_width=True,
        )

        donut = render_donut_chart(
            source,
            column,
            "Distribuição no recorte",
            top_n,
            show_others,
        )

        right.plotly_chart(
            donut,
            use_container_width=True,
        )

        result[name + " — distribuição"] = donut

    else:
        st.plotly_chart(
            figure,
            use_container_width=True,
        )

    return result


def render_page(page_id):
    if page_id not in PAGE_INFO:
        st.error("Página não reconhecida.")
        return

    title, subtitle = PAGE_INFO[page_id]

    st.title(title)
    st.caption(subtitle)

    context = st.session_state.get("_page_context")

    if context is None:
        st.error(
            "O contexto da página não foi inicializado. "
            "Abra o aplicativo pelo app.py."
        )
        return

    if not context["valid"] or not context["additional"]:
        st.info(
            "Selecione o período e pelo menos um filtro "
            "adicional para visualizar os indicadores."
        )
        return

    df = context["cut"].copy()

    if page_id == "corretivas":
        st.caption(
            "Escopo desta página: somente corretivas, "
            "respeitando os filtros comuns."
        )

        df = df.loc[
            df["Tipo"].eq("Corretiva")
        ].copy()

    if df.empty:
        st.info(
            "Nenhum registro encontrado para os filtros "
            "selecionados nesta página."
        )
        return

    spec = context["spec"]
    start, end = spec["period"]

    st.caption(
        f"{start:%d/%m/%Y} a {end:%d/%m/%Y} • "
        f"{len(df)} tarefas no recorte"
    )

    render_filter_summary(context)

    prefix = "dash_" + page_id + "_"
    values = calculate_kpis(df)

    with st.expander(
        "Personalizar indicadores",
        expanded=False,
    ):
        selected_kpis = persist_widget(
            "multiselect",
            "Indicadores exibidos",
            prefix + "kpis",
            options=list(values),
            default=[],
        )

    if selected_kpis:
        st.subheader("Resumo do período")

        render_kpi_cards(
            selected_kpis,
            values,
        )

    else:
        st.info(
            "Selecione ao menos um indicador "
            "em Personalizar indicadores."
        )

    available = available_chart_names(
        df,
        page_id,
    )

    with st.expander(
        "Visualizações e exportação",
        expanded=True,
    ):
        selected_charts = persist_widget(
            "multiselect",
            "Gráficos exibidos",
            prefix + "charts",
            options=available,
            default=[],
            disabled=not selected_kpis,
        )

        left, right = st.columns(2)

        with left:
            if st.button(
                "Selecionar tudo",
                key=prefix + "select_all",
                disabled=not selected_kpis,
            ):
                st.session_state[
                    prefix + "charts_saved"
                ] = list(available)

                st.rerun()

        with right:
            if st.button(
                "Limpar seleção de gráficos",
                key=prefix + "clear_charts",
            ):
                st.session_state[
                    prefix + "charts_saved"
                ] = []

                st.rerun()

        top_n_global = persist_widget(
            "number_input",
            "Top N padrão global",
            "dash_global_top",
            min_value=1,
            max_value=100,
            value=10,
        )

        export_slot = st.container()

    figures = {}
    associations = {}

    charts_to_render = (
        selected_charts
        if selected_kpis
        else []
    )

    for name in charts_to_render:
        st.subheader(name)

        chart_hash = hashlib.sha1(
            name.encode("utf-8")
        ).hexdigest()[:10]

        key = prefix + chart_hash

        associated_kpis = ASSOCIATIONS.get(
            name,
            {"Total de tarefas"},
        )

        if name == "Evolução no período":
            figure = render_evolution(
                df,
                spec,
                key,
            )

            st.plotly_chart(
                figure,
                use_container_width=True,
            )

            figures[name] = figure
            associations[name] = associated_kpis

        elif name == "Participação do recorte no universo":
            figure = render_universe(
                df,
                context,
                page_id,
                key,
            )

            st.plotly_chart(
                figure,
                use_container_width=True,
            )

            figures[name] = figure
            associations[name] = associated_kpis

        else:
            ranking_figures = render_ranking_block(
                df,
                name,
                key,
                top_n_global,
            )

            for figure_name, figure in ranking_figures.items():
                figures[figure_name] = figure
                associations[figure_name] = associated_kpis

    with export_slot:
        st.markdown("Exportação PDF")

        render_export(
            figures,
            associations,
            values,
            page_id,
        )

    if any(
        "garantia" in name.lower()
        for name in selected_kpis
    ):
        st.caption(
            "Garantia: a base atual utiliza a situação "
            "da data limite em relação a hoje. "
            "A cobertura histórica da chamada "
            "ainda precisa ser validada."
        )

    if page_id == "maquinas":
        st.caption(
            "Comparação Máquina A × Máquina B: "
            "prevista para a próxima entrega. "
            "Esta página já oferece rankings por equipamento."
        )

    signature_text = (
        repr(spec)
        + page_id
        + repr(df.index.tolist())
    )

    signature = hashlib.sha1(
        signature_text.encode("utf-8")
    ).hexdigest()

    render_detail(
        df,
        page_id,
        signature,
    )
