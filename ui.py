import hashlib
import math
import unicodedata

import streamlit as st

from charts import (
    render_evolution_chart,
    render_horizontal_ranking,
    render_donut_chart,
    render_cut_donut,
    render_pareto_chart,
    render_abc_donut,
    abc_table,
    category_counts,
    revise_bar_labels,
)
from filters import apply_filters, COLUMNS
from kpis import (
    calculate_kpis,
    render_kpi_cards,
    occurrence_frame,
)
from pdf_export import generate_pdf_report
from comparison import (
    comparison_base,
    split_machines,
    comparison_evolution,
    comparison_bars,
    comparison_share,
    comparison_occurrences,
)


def apply_theme():
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1550px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        .kpi-card {
            background: var(--secondary-background-color, #fff);
            border: 1px solid #DCE4EC;
            border-radius: 12px;
            padding: 18px;
            min-height: 145px;
            box-sizing: border-box;
            margin-bottom: 14px;
        }

        .kpi-label {
            font-size: .83rem;
            opacity: .8;
            margin-bottom: 12px;
        }

        .kpi-value {
            font-weight: 650;
            line-height: 1.25;
            overflow-wrap: anywhere;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def widget(kind, label, key, **kwargs):
    saved = key + "_saved"

    if saved in st.session_state:
        value = st.session_state[saved]
        options = kwargs.get("options")

        if options is not None:
            if kind == "multiselect":
                value = [
                    item for item in value
                    if item in options
                ]
            elif len(options) and value not in options:
                value = options[0]

        if kind == "number_input":
            minimum = kwargs.get("min_value")
            maximum = kwargs.get("max_value")

            if minimum is not None:
                value = max(minimum, value)

            if maximum is not None:
                value = min(maximum, value)

        st.session_state[key] = value
        kwargs.pop("default", None)
        kwargs.pop("value", None)

    def save():
        st.session_state[saved] = st.session_state[key]

    result = getattr(st, kind)(
        label,
        key=key,
        on_change=save,
        **kwargs,
    )

    st.session_state[saved] = result
    return result


def context(
    page_id,
    title,
    subtitle,
    corrective=False,
):
    st.title(title)
    st.caption(subtitle)

    ctx = st.session_state.get("_page_context")

    if ctx is None:
        st.error("Abra o aplicativo pelo app.py.")
        return None

    if not ctx["valid"] or not ctx["additional"]:
        st.info(
            "Selecione o período e pelo menos um filtro "
            "adicional na barra lateral."
        )
        return None

    data = ctx["cut"].copy()

    if corrective:
        data = data.loc[
            data["Tipo"].eq("Corretiva")
        ].copy()

    if data.empty and page_id != "maquinas":
        st.info(
            "Nenhum registro encontrado neste recorte."
        )
        return None

    spec = ctx["spec"]
    start, end = spec["period"]

    st.caption(
        f"{start:%d/%m/%Y} a {end:%d/%m/%Y}"
        f" • {len(data)} tarefas no recorte"
    )

    labels = dict(
        zip(
            ctx["raw"]["Máquina"],
            ctx["raw"]["Seleção da máquina"],
        )
    )

    active = []

    for column in ["Tipo"] + list(COLUMNS):
        selected = spec.get(column)

        if not selected:
            continue

        if isinstance(selected, str) and selected == "Todas":
            continue

        if isinstance(selected, str):
            text = selected
        else:
            text = ", ".join(
                str(labels.get(value, value))
                if column == "Máquina"
                else str(value)
                for value in selected
            )

        active.append(column + ": " + text)

    if active:
        st.caption(" | ".join(active))

    return {
        "id": page_id,
        "raw": ctx["raw"],
        "spec": spec,
        "df": data,
        "figures": {},
        "associations": {},
        "key": "dash_" + page_id + "_",
    }


def chart_key(c, name):
    return (
        c["key"]
        + hashlib.sha1(
            name.encode()
        ).hexdigest()[:10]
    )


def registry(c, name, fig, kpis):
    if fig is None:
        st.info(
            "Sem ocorrências válidas para esta análise."
        )
        return

    revise_bar_labels(fig)

    # Não exibir miniaturas de navegação abaixo dos eixos.
    fig.update_xaxes(
        rangeslider=dict(visible=False)
    )

    c["figures"][name] = fig
    c["associations"][name] = set(kpis)

    st.plotly_chart(
        fig,
        use_container_width=True,
        key=chart_key(
            c,
            "figure_" + name,
        ),
    )


def configuration(
    c,
    kpi_options,
    chart_options,
):
    values = calculate_kpis(c["df"])

    available_kpis = [
        name for name in kpi_options
        if name in values
    ]

    with st.expander(
        "Indicadores, análises e PDF",
        expanded=True,
    ):
        left, right = st.columns(2)

        if left.button(
            "Selecionar todos os indicadores",
            key=c["key"] + "all_kpis",
        ):
            st.session_state[
                c["key"] + "kpis_saved"
            ] = list(available_kpis)

        if right.button(
            "Limpar indicadores",
            key=c["key"] + "none_kpis",
        ):
            st.session_state[
                c["key"] + "kpis_saved"
            ] = []

        selected_kpis = widget(
            "multiselect",
            "Indicadores desta página",
            c["key"] + "kpis",
            options=available_kpis,
            default=[],
        )

        left, right = st.columns(2)

        if left.button(
            "Selecionar todas as análises",
            key=c["key"] + "all",
            disabled=not selected_kpis,
        ):
            st.session_state[
                c["key"] + "analyses_saved"
            ] = list(chart_options)

        if right.button(
            "Limpar análises",
            key=c["key"] + "none",
        ):
            st.session_state[
                c["key"] + "analyses_saved"
            ] = []

        selected = widget(
            "multiselect",
            "Análises desta página",
            c["key"] + "analyses",
            options=chart_options,
            default=[],
            disabled=not selected_kpis,
        )

        top = widget(
            "number_input",
            "Top N padrão global",
            "dash_global_top",
            min_value=1,
            value=10,
            step=1,
        )

        export_slot = st.container()

    c.update(
        values=values,
        kpis=selected_kpis,
        selected=(
            selected
            if selected_kpis
            else []
        ),
        top=int(top),
        export_slot=export_slot,
    )

    if selected_kpis:
        st.subheader("Indicadores do recorte")
        render_kpi_cards(
            selected_kpis,
            values,
        )
    else:
        st.info(
            "Selecione indicadores para habilitar "
            "as análises desta página."
        )

    if any(
        "garantia" in name.lower()
        for name in selected_kpis
    ):
        st.warning(
            "Garantia representa a situação atual da data limite. "
            "A cobertura histórica da chamada ainda não foi definida."
        )

    return c


def evolution(
    c,
    name="Evolução no período",
):
    key = chart_key(c, name)
    left, right = st.columns(2)

    with left:
        granularity = widget(
            "selectbox",
            "Agrupamento",
            key + "gran",
            options=[
                "Diária",
                "Semanal",
                "Mensal",
            ],
        )

    with right:
        visual = widget(
            "selectbox",
            "Visual",
            key + "visual",
            options=[
                "Barras",
                "Linha",
                "Barras + linha acumulada",
            ],
        )

    fig = render_evolution_chart(
        c["df"],
        granularity,
        visual,
        c["spec"]["period"],
    )

    registry(
        c,
        name,
        fig,
        {
            "Total de tarefas",
            "Preventivas",
            "Corretivas",
            "% Preventivas",
            "% Corretivas",
        },
    )


def ranking(
    c,
    column,
    title,
    associated,
    kind=None,
):
    source = c["df"]

    if kind:
        source = source.loc[
            source["Tipo"].eq(kind)
        ]

    if source.empty or column not in source.columns:
        st.info(
            "Não há registros para "
            + title.lower()
            + "."
        )
        return

    counts = category_counts(
        source,
        column,
    )

    if counts.empty:
        st.info(
            "Não há ocorrências válidas para "
            + title.lower()
            + "."
        )
        return

    key = chart_key(c, title)
    st.markdown("### " + title)

    with st.expander("Ajustes — " + title):
        own = widget(
            "checkbox",
            "Definir Top N individual",
            key + "override",
            value=False,
        )

        if own:
            n = widget(
                "number_input",
                "Top N individual",
                key + "n",
                min_value=1,
                max_value=len(counts),
                value=min(10, len(counts)),
                step=1,
            )
        else:
            n = c["top"]

        n = int(n)

        pair = widget(
            "checkbox",
            "Mostrar distribuição do recorte",
            key + "pair",
            value=False,
        )

        others = widget(
            "checkbox",
            "Agrupar restante em Outras",
            key + "others",
            value=True,
        )

    bars = render_horizontal_ranking(
        source,
        column,
        title,
        n,
    )

    st.caption(
        f"{len(counts)} categorias no recorte"
        f" • {min(n, len(counts))} exibidas no ranking"
    )

    if not pair:
        registry(
            c,
            title,
            bars,
            associated,
        )
        return

    donut_title = (
        title
        + " — distribuição no recorte"
    )

    donut = render_donut_chart(
        source,
        column,
        donut_title,
        n,
        others,
    )

    entries = min(n, len(counts))

    if others and len(counts) > n:
        entries += 1

    if entries <= 10:
        left, right = st.columns([1.1, 1])

        with left:
            registry(
                c,
                title,
                bars,
                associated,
            )

        with right:
            registry(
                c,
                donut_title,
                donut,
                associated,
            )
    else:
        registry(
            c,
            title,
            bars,
            associated,
        )

        st.markdown(
            "#### Distribuição do recorte"
        )

        st.caption(
            f"{entries} entradas na rosca. "
            "A distribuição ocupa uma área própria."
        )

        registry(
            c,
            donut_title,
            donut,
            associated,
        )

    if not others and len(counts) > n:
        st.caption(
            "Sem “Outras”, os percentuais da rosca "
            "consideram somente as categorias exibidas."
        )


def participation(c):
    key = c["key"] + "universe"

    st.markdown("### Recorte × universo")

    mode = widget(
        "selectbox",
        "Universo de comparação",
        key,
        options=[
            "Todas as tarefas no período",
            "Mesmo tipo no período",
            "Personalizado",
        ],
    )

    spec = {
        "period": c["spec"]["period"],
        "Tipo": "Todas",
    }

    if mode == "Mesmo tipo no período":
        types = c["df"]["Tipo"].unique()

        spec["Tipo"] = (
            types[0]
            if len(types) == 1
            else c["spec"].get("Tipo", "Todas")
        )

    elif mode == "Personalizado":
        candidates = [
            column
            for column in ["Tipo"] + list(COLUMNS)
            if c["spec"].get(column)
            and c["spec"].get(column) != "Todas"
        ]

        keep = widget(
            "multiselect",
            "Manter filtros no universo",
            key + "keep",
            options=candidates,
            default=[],
        )

        for column in keep:
            spec[column] = c["spec"][column]

    universe = apply_filters(
        c["raw"],
        spec,
    )

    st.caption(
        f"{len(c['df'])} tarefas no recorte"
        f" / {len(universe)} no universo"
        " • mesmo período"
    )

    registry(
        c,
        "Participação do recorte no universo",
        render_cut_donut(
            universe,
            c["df"],
        ),
        {"Total de tarefas"},
    )


def composition(c, title):
    registry(
        c,
        title,
        render_donut_chart(
            c["df"],
            "Tipo",
            title,
            10,
            True,
        ),
        {
            "Total de tarefas",
            "Preventivas",
            "Corretivas",
            "% Preventivas",
            "% Corretivas",
        },
    )


def _category_rows(
    df,
    column,
    members,
):
    if column in {"Problema", "Peça"}:
        occurrences = occurrence_frame(
            df,
            column,
        )

        indexes = occurrences.loc[
            occurrences[column].isin(members)
        ].index.unique()

        return df.loc[
            df.index.isin(indexes)
        ].copy()

    values = (
        df[column]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    return df.loc[
        values.isin(members)
    ].copy()


def concentration(
    c,
    column,
    title,
    associated,
    kind=None,
    drilldown=(),
):
    source = c["df"]

    if kind:
        source = source.loc[
            source["Tipo"].eq(kind)
        ]

    if source.empty or column not in source.columns:
        st.info(
            "Não há registros para "
            + title.lower()
            + "."
        )
        return

    key = chart_key(c, title)
    st.markdown("### " + title)

    base = widget(
        "selectbox",
        "Base da análise ABC",
        key + "base",
        options=[
            "Recorte atual",
            "Universo de comparação",
        ],
    )

    analysis = source.copy()
    highlight = None

    if base == "Universo de comparação":
        filter_column = (
            "Máquina"
            if column == "Rótulo da máquina"
            else column
        )

        analysis = apply_filters(
            c["raw"],
            c["spec"],
            ignore=(filter_column,),
        )

        if kind:
            analysis = analysis.loc[
                analysis["Tipo"].eq(kind)
            ]

        highlight = set(
            category_counts(
                source,
                column,
            ).index
        )

        st.caption(
            "Universo: mesmo período e demais filtros, "
            f"sem o filtro de {filter_column.lower()}. "
            "Categorias do recorte recebem contorno escuro."
        )

    counts = category_counts(
        analysis,
        column,
    )

    if counts.empty:
        st.info(
            "Não há categorias válidas para esta análise."
        )
        return

    with st.expander(
        "Ajustes do Pareto principal — " + title,
        expanded=True,
    ):
        all_items = widget(
            "checkbox",
            "Exibir todas as categorias no Pareto principal",
            key + "show_all",
            value=False,
        )

        n = widget(
            "number_input",
            "Top N do Pareto principal",
            key + "principal_top",
            min_value=1,
            max_value=len(counts),
            value=min(c["top"], len(counts)),
            step=1,
            disabled=all_items,
        )

        left, right = st.columns(2)

        a_percent = left.number_input(
            "Limite da classe A (%)",
            min_value=1,
            max_value=98,
            value=80,
            step=1,
            key=key + "a",
        )

        b_percent = right.number_input(
            "Limite da classe B (%)",
            min_value=2,
            max_value=100,
            value=95,
            step=1,
            key=key + "b",
        )

    if b_percent <= a_percent:
        st.warning(
            "O limite da classe B deve ser maior que o da A."
        )
        return

    a_limit = a_percent / 100
    b_limit = b_percent / 100

    abc = abc_table(
        counts,
        a_limit,
        b_limit,
    )

    unit = (
        "ocorrências"
        if column in {"Problema", "Peça"}
        else "tarefas"
    )

    total = int(
        abc["Quantidade"].sum()
    )

    top_n = (
        None
        if all_items
        else int(n)
    )

    registry(
        c,
        title,
        render_pareto_chart(
            counts,
            title,
            top_n,
            highlight,
            a_limit,
            b_limit,
            unit,
        ),
        associated,
    )

    shown = (
        abc
        if top_n is None
        else abc.head(top_n)
    )

    shown_total = int(
        shown["Quantidade"].sum()
    )

    st.caption(
        f"Base: {base.lower()}"
        f" • Exibindo {len(shown)} de {len(abc)} categorias"
        f" — {shown_total / total * 100:.2f}% do volume"
        f" ({total} {unit} na base). "
        "O Top N não altera a classificação ABC."
    )

    st.markdown(
        "#### Composição da Curva ABC"
    )

    registry(
        c,
        title + " — classes",
        render_abc_donut(
            abc,
            title + " — classes A, B e C",
            unit,
        ),
        associated,
    )

    summary = (
        abc.groupby("Classe")
        .agg(
            Categorias=("Categoria", "nunique"),
            Volume=("Quantidade", "sum"),
        )
        .reindex(["A", "B", "C"])
        .fillna(0)
    )

    for slot, letter in zip(
        st.columns(3),
        ["A", "B", "C"],
    ):
        volume = int(
            summary.loc[letter, "Volume"]
        )
        items = int(
            summary.loc[letter, "Categorias"]
        )

        slot.metric(
            "Classe " + letter,
            f"{volume:,}".replace(",", "."),
            (
                f"{items} categoria(s)"
                f" • {volume / total * 100:.2f}%"
            ),
            delta_color="off",
        )

    with st.expander(
        "Tabela de classificação ABC"
    ):
        display_abc = abc.rename(
            columns={
                "Participação": "Participação (%)",
                "Acumulado %": "Acumulado (%)",
            }
        ).copy()

        for percentage_column in [
            "Participação (%)",
            "Acumulado (%)",
        ]:
            display_abc[percentage_column] = (
                display_abc[percentage_column]
                .round(2)
            )

        st.dataframe(
            display_abc,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Categoria": st.column_config.TextColumn(
                    "Categoria",
                    width="large",
                ),
                "Quantidade": st.column_config.NumberColumn(
                    "Quantidade",
                    format="%d",
                ),
                "Participação (%)": st.column_config.NumberColumn(
                    "Participação (%)",
                    format="%.2f",
                ),
                "Acumulado": st.column_config.NumberColumn(
                    "Acumulado",
                    format="%d",
                ),
                "Acumulado (%)": st.column_config.NumberColumn(
                    "Acumulado (%)",
                    format="%.2f",
                ),
                "Classe": st.column_config.TextColumn(
                    "Classe",
                ),
            },
        )

    available = [
        letter for letter in ["A", "B", "C"]
        if summary.loc[letter, "Categorias"] > 0
    ]

    if not drilldown or not available:
        return

    st.markdown(
        "#### Detalhar uma classe"
    )

    selected = widget(
        "selectbox",
        "Classe para detalhar",
        key + "class",
        options=available,
        format_func=lambda letter: "Classe " + letter,
    )

    members = abc.loc[
        abc["Classe"].eq(selected),
        "Categoria",
    ].tolist()

    subset = _category_rows(
        analysis,
        column,
        members,
    )

    options = [
        item for item in drilldown
        if item in subset.columns
    ]

    if subset.empty or not options:
        st.info(
            "Sem registros válidos para o detalhamento."
        )
        return

    st.caption(
        f"Classe {selected}: {len(members)} categorias"
        f" • {len(subset)} tarefas relacionadas."
    )

    breakdown = widget(
        "selectbox",
        "Analisar a classe por",
        key + "breakdown",
        options=options,
    )

    inner_counts = category_counts(
        subset,
        breakdown,
    )

    if inner_counts.empty:
        st.info(
            "Sem ocorrências válidas neste detalhamento."
        )
        return

    # Mantém controles separados por classe e dimensão.
    suffix = hashlib.sha1(
        (selected + "|" + breakdown).encode()
    ).hexdigest()[:12]

    inner_key = (
        key
        + "_inner_"
        + suffix
    )

    with st.expander(
        "Ajustes do Pareto interno — " + breakdown,
        expanded=True,
    ):
        inner_all = widget(
            "checkbox",
            "Exibir todas as categorias neste detalhamento",
            inner_key + "all",
            value=False,
        )

        inner_n = widget(
            "number_input",
            "Top N deste detalhamento",
            inner_key + "top",
            min_value=1,
            max_value=len(inner_counts),
            value=min(
                c["top"],
                len(inner_counts),
            ),
            step=1,
            disabled=inner_all,
        )

    inner_top_n = (
        None
        if inner_all
        else int(inner_n)
    )

    inner_unit = (
        "ocorrências"
        if breakdown in {"Problema", "Peça"}
        else "tarefas"
    )

    inner_title = (
        title
        + f" — classe {selected}"
        + f" — {breakdown.lower()}"
    )

    registry(
        c,
        inner_title,
        render_pareto_chart(
            inner_counts,
            inner_title,
            inner_top_n,
            None,
            a_limit,
            b_limit,
            inner_unit,
        ),
        associated,
    )

    inner_shown = (
        inner_counts
        if inner_top_n is None
        else inner_counts.head(inner_top_n)
    )

    inner_total = int(
        inner_counts.sum()
    )

    coverage = (
        float(inner_shown.sum()) / inner_total * 100
        if inner_total
        else 0
    )

    st.caption(
        f"Exibindo {len(inner_shown)}"
        f" de {len(inner_counts)} categorias"
        f" — {coverage:.2f}% do volume deste detalhamento"
        f" ({inner_total} {inner_unit})."
    )

    st.caption(
        "O acumulado deste detalhamento usa somente o volume "
        "da classe selecionada. As cores indicam uma ABC interna, "
        "sem alterar a classificação original. "
        "O Top N interno e a opção de exibir todas são "
        "independentes dos controles principais."
    )


def norm_header(value):
    text = unicodedata.normalize(
        "NFKD",
        str(value).strip().lower(),
    )

    return " ".join(
        "".join(
            character
            for character in text
            if not unicodedata.combining(character)
        ).split()
    )


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
            if norm_header(column) in markers
        ),
        None,
    )

    if cutoff is not None:
        shown = [
            column
            for column in columns[:cutoff]
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

        shown = [
            column for column in preferred
            if column in columns
        ]

    if "Garantia" in columns and "Garantia" not in shown:
        shown.append("Garantia")

    return shown, cutoff is not None


def details(c):
    with st.expander(
        "Detalhamento dos registros",
        expanded=False,
    ):
        data = c["df"]

        shown, found = detail_columns(
            list(data.columns)
        )

        if not found:
            st.caption(
                "Cabeçalho patrimonial não localizado; "
                "exibindo somente as colunas essenciais."
            )

        prefix = c["key"] + "detail"

        size = st.selectbox(
            "Registros por página",
            [15, 25, 50, 100],
            key=prefix + "size",
        )

        signature = hashlib.sha1(
            (
                repr(c["spec"])
                + repr(data.index.tolist())
                + str(size)
            ).encode()
        ).hexdigest()

        pages = max(
            1,
            math.ceil(len(data) / size),
        )

        if (
            st.session_state.get(prefix + "signature")
            != signature
        ):
            st.session_state[prefix + "page"] = 1
            st.session_state[prefix + "signature"] = signature

        current_page = st.session_state.get(
            prefix + "page",
            1,
        )

        if not 1 <= current_page <= pages:
            st.session_state[prefix + "page"] = 1

        page = int(
            st.number_input(
                "Página",
                min_value=1,
                max_value=pages,
                step=1,
                key=prefix + "page",
            )
        )

        ordered = data.sort_values(
            "Data da tarefa",
            ascending=False,
        )

        st.caption(
            f"{len(data)} registros"
            f" • página {page} de {pages}"
        )

        st.dataframe(
            ordered.iloc[
                (page - 1) * size:page * size
            ][shown],
            hide_index=True,
            use_container_width=True,
        )


def finish(c):
    with c["export_slot"]:
        st.markdown(
            "#### Exportação PDF"
        )

        key = c["key"] + "pdf"

        names = widget(
            "multiselect",
            "Gráficos para o PDF",
            key + "charts",
            options=list(c["figures"]),
            default=[],
        )

        if not names:
            allowed = set(c["values"])
        else:
            allowed = set().union(
                *(
                    c["associations"][name]
                    for name in names
                )
            )

        selected = widget(
            "multiselect",
            "Indicadores para o PDF",
            key + "kpis",
            options=[
                name for name in c["values"]
                if name in allowed
            ],
            default=[],
        )

        st.caption(
            "Os indicadores exportados pertencem ao recorte da página. "
            "Gráficos do universo podem usar uma base maior. "
            "Na comparação, os indicadores são do conjunto A + B."
        )

        count = widget(
            "selectbox",
            "Gráficos por página",
            key + "count",
            options=[1, 2, 3, 4],
        )

        if st.button(
            "Gerar PDF",
            key=key + "generate",
            disabled=not (names or selected),
        ):
            try:
                pdf = generate_pdf_report(
                    c["values"],
                    selected,
                    {
                        name: c["figures"][name]
                        for name in names
                    },
                    count,
                )

                st.download_button(
                    "Baixar PDF",
                    pdf,
                    "painel_" + c["id"] + ".pdf",
                    "application/pdf",
                    key=key + "download",
                )

            except Exception as error:
                st.error(
                    "Não foi possível gerar o PDF. "
                    "Confira o diagnóstico abaixo."
                )
                st.code(str(error))

    details(c)


def render_monitoramento():
    c = context(
        "monitoramento",
        "Monitoramento",
        "Visão consolidada de volume, composição e corretivas.",
    )

    if c is None:
        return

    configuration(
        c,
        [
            "Total de tarefas",
            "Preventivas",
            "Corretivas",
            "% Preventivas",
            "% Corretivas",
            "Máquinas atendidas",
            "Técnicos envolvidos",
        ],
        [
            "Evolução da operação",
            "Composição das manutenções",
            "Equipamentos com mais corretivas",
            "Recorte × universo",
        ],
    )

    if "Evolução da operação" in c["selected"]:
        evolution(
            c,
            "Evolução da operação",
        )

    if "Composição das manutenções" in c["selected"]:
        composition(
            c,
            "Preventivas × corretivas",
        )

    if "Equipamentos com mais corretivas" in c["selected"]:
        ranking(
            c,
            "Rótulo da máquina",
            "Equipamentos com mais corretivas",
            {"Corretivas", "Máquinas atendidas"},
            "Corretiva",
        )

    if "Recorte × universo" in c["selected"]:
        participation(c)

    finish(c)


def render_analise_tarefas():
    c = context(
        "analise_tarefas",
        "Análise de tarefas",
        "Serviços executados, responsáveis e volume no período.",
    )

    if c is None:
        return

    configuration(
        c,
        [
            "Total de tarefas",
            "Preventivas",
            "Corretivas",
            "% Preventivas",
            "% Corretivas",
            "Técnicos envolvidos",
            "Máquinas atendidas",
        ],
        [
            "Serviços executados",
            "Ritmo dos atendimentos",
            "Distribuição por responsável",
            "Distribuição por equipamento",
            "Concentração de tarefas por equipamento",
            "Concentração de tarefas por responsável",
        ],
    )

    if "Serviços executados" in c["selected"]:
        ranking(
            c,
            "Tarefa",
            "Serviços executados",
            {
                "Total de tarefas",
                "Preventivas",
                "Corretivas",
            },
        )

    if "Ritmo dos atendimentos" in c["selected"]:
        evolution(
            c,
            "Ritmo dos atendimentos",
        )

    if "Distribuição por responsável" in c["selected"]:
        ranking(
            c,
            "Técnico",
            "Tarefas por responsável",
            {
                "Total de tarefas",
                "Técnicos envolvidos",
            },
        )

    if "Distribuição por equipamento" in c["selected"]:
        ranking(
            c,
            "Rótulo da máquina",
            "Tarefas por equipamento",
            {
                "Total de tarefas",
                "Máquinas atendidas",
            },
        )

    if "Concentração de tarefas por equipamento" in c["selected"]:
        concentration(
            c,
            "Rótulo da máquina",
            "Concentração de tarefas por equipamento",
            {
                "Total de tarefas",
                "Máquinas atendidas",
            },
            None,
            ["Tarefa", "Técnico"],
        )

    if "Concentração de tarefas por responsável" in c["selected"]:
        concentration(
            c,
            "Técnico",
            "Concentração de tarefas por responsável",
            {
                "Total de tarefas",
                "Técnicos envolvidos",
            },
            None,
            ["Rótulo da máquina", "Tarefa"],
        )

    finish(c)


def render_corretivas():
    c = context(
        "corretivas",
        "Corretivas",
        "Falhas e tratamentos. Apenas tarefas corretivas.",
        True,
    )

    if c is None:
        return

    configuration(
        c,
        [
            "Corretivas",
            "Máquinas atendidas",
            "Técnicos envolvidos",
            "Problema mais frequente",
            "Peça mais trocada",
            "Corretivas em garantia",
            "Corretivas fora da garantia",
        ],
        [
            "Falhas relatadas",
            "Peças utilizadas",
            "Serviços corretivos",
            "Equipamentos envolvidos",
            "Evolução das corretivas",
        ],
    )

    if "Falhas relatadas" in c["selected"]:
        ranking(
            c,
            "Problema",
            "Falhas relatadas",
            {
                "Corretivas",
                "Problema mais frequente",
            },
        )

    if "Peças utilizadas" in c["selected"]:
        ranking(
            c,
            "Peça",
            "Peças utilizadas",
            {
                "Corretivas",
                "Peça mais trocada",
            },
        )

    if "Serviços corretivos" in c["selected"]:
        ranking(
            c,
            "Tarefa",
            "Serviços corretivos",
            {"Corretivas"},
        )

    if "Equipamentos envolvidos" in c["selected"]:
        ranking(
            c,
            "Rótulo da máquina",
            "Equipamentos envolvidos em corretivas",
            {
                "Corretivas",
                "Máquinas atendidas",
            },
        )

    if "Evolução das corretivas" in c["selected"]:
        evolution(
            c,
            "Evolução das corretivas",
        )

    missing = (
        c["df"]["Problema"]
        .fillna("")
        .astype(str)
        .str.strip()
        .isin([
            "",
            "Não informado",
            "Nao informado",
        ])
    )

    if missing.any():
        st.warning(
            f"{int(missing.sum())} corretiva(s) "
            "sem problema válido. "
            "Não entram no ranking de falhas."
        )

    finish(c)


def render_clientes_regioes():
    c = context(
        "clientes_regioes",
        "Clientes e regiões",
        "Distribuição dos atendimentos por cliente e localização.",
    )

    if c is None:
        return

    available = [
        column
        for column in [
            "Cliente",
            "Estado",
            "Região",
            "Cidade",
        ]
        if (
            c["df"][column]
            .fillna("")
            .astype(str)
            .str.strip()
            .ne("")
            .any()
        )
    ]

    if not available:
        st.info(
            "Não há cliente ou localização "
            "preenchidos neste recorte."
        )

    with st.expander(
        "Refinar cliente e localização nesta página",
        expanded=False,
    ):
        for column in available:
            series = (
                c["df"][column]
                .fillna("")
                .astype(str)
                .str.strip()
            )

            options = sorted(
                series.loc[
                    series.ne("")
                ].unique()
            )

            chosen = widget(
                "multiselect",
                column + " nesta página",
                c["key"] + "local_" + column,
                options=options,
                default=[],
            )

            if chosen:
                c["df"] = c["df"].loc[
                    series.isin(chosen)
                ].copy()

    if c["df"].empty:
        st.info(
            "Nenhum atendimento corresponde "
            "ao refinamento local."
        )
        return

    dims = [
        column for column in available
        if (
            c["df"][column]
            .fillna("")
            .astype(str)
            .str.strip()
            .ne("")
            .any()
        )
    ]

    options = [
        "Distribuição por " + column.lower()
        for column in dims
    ] + [
        "Composição local",
        "Participação no universo",
    ]

    configuration(
        c,
        [
            "Total de tarefas",
            "Máquinas atendidas",
            "Preventivas",
            "Corretivas",
            "% Corretivas",
        ],
        options,
    )

    for column in dims:
        analysis_name = (
            "Distribuição por "
            + column.lower()
        )

        if analysis_name in c["selected"]:
            ranking(
                c,
                column,
                "Atendimentos por " + column.lower(),
                {
                    "Total de tarefas",
                    "Máquinas atendidas",
                },
            )

    if "Composição local" in c["selected"]:
        composition(
            c,
            "Composição das manutenções no recorte local",
        )

    if "Participação no universo" in c["selected"]:
        participation(c)

    finish(c)


def render_maquinas():
    c = context(
        "maquinas",
        "Máquinas",
        "Explore uma máquina ou compare duas no mesmo contexto.",
    )

    if c is None:
        return

    base = comparison_base(
        c["raw"],
        c["spec"],
    )

    if base.empty:
        st.info(
            "Nenhuma máquina com tarefas neste contexto."
        )
        return

    st.caption(
        "As seleções abaixo substituem somente o filtro "
        "de máquina da lateral. Os demais filtros "
        "continuam aplicados."
    )

    labels = dict(
        zip(
            c["raw"]["Máquina"],
            c["raw"]["Seleção da máquina"],
        )
    )

    codes = sorted(
        base["Máquina"].unique()
    )

    mode = widget(
        "radio",
        "Modo de análise",
        c["key"] + "mode",
        options=[
            "Uma máquina",
            "Comparar A × B",
        ],
        horizontal=True,
    )

    def label_func(code):
        if code is None:
            return "Selecione uma máquina"

        return labels.get(code, code)

    code_a = widget(
        "selectbox",
        (
            "Máquina A"
            if mode == "Comparar A × B"
            else "Equipamento"
        ),
        c["key"] + "machine_a",
        options=[None] + codes,
        format_func=label_func,
    )

    if code_a is None:
        st.info(
            "Escolha o equipamento para iniciar a análise."
        )
        return

    a = base.loc[
        base["Máquina"].eq(code_a)
    ].copy()

    if mode == "Uma máquina":
        c["df"] = a

        st.subheader(
            labels.get(code_a, code_a)
        )

        configuration(
            c,
            [
                "Total de tarefas",
                "Preventivas",
                "Corretivas",
                "% Corretivas",
                "Problema mais frequente",
                "Peça mais trocada",
            ],
            [
                "Histórico do equipamento",
                "Composição do equipamento",
                "Problemas do equipamento",
                "Peças do equipamento",
                "Serviços no equipamento",
            ],
        )

        if "Histórico do equipamento" in c["selected"]:
            evolution(
                c,
                "Histórico do equipamento",
            )

        if "Composição do equipamento" in c["selected"]:
            composition(
                c,
                "Composição do equipamento",
            )

        if "Problemas do equipamento" in c["selected"]:
            ranking(
                c,
                "Problema",
                "Problemas do equipamento",
                {
                    "Corretivas",
                    "Problema mais frequente",
                },
            )

        if "Peças do equipamento" in c["selected"]:
            ranking(
                c,
                "Peça",
                "Peças do equipamento",
                {
                    "Corretivas",
                    "Peça mais trocada",
                },
            )

        if "Serviços no equipamento" in c["selected"]:
            ranking(
                c,
                "Tarefa",
                "Serviços no equipamento",
                {"Total de tarefas"},
            )

    else:
        code_b = widget(
            "selectbox",
            "Máquina B",
            c["key"] + "machine_b",
            options=[
                None
            ] + [
                code for code in codes
                if code != code_a
            ],
            format_func=label_func,
        )

        if code_b is None:
            st.info(
                "Escolha uma segunda máquina "
                "diferente da primeira."
            )
            return

        a, b = split_machines(
            base,
            code_a,
            code_b,
        )

        c["df"] = base.loc[
            base["Máquina"].isin([
                code_a,
                code_b,
            ])
        ].copy()

        label_a = labels.get(code_a, code_a)
        label_b = labels.get(code_b, code_b)

        configuration(
            c,
            [
                "Total de tarefas",
                "Preventivas",
                "Corretivas",
                "% Corretivas",
                "Máquinas atendidas",
                "Problema mais frequente",
                "Peça mais trocada",
            ],
            [
                "Volume A × B",
                "Evolução A × B",
                "Participação A × B",
                "Problemas A × B",
                "Peças A × B",
            ],
        )

        if c["kpis"]:
            st.subheader(
                "Indicadores individuais"
            )

            left, right = st.columns(2)

            for slot, data, label in [
                (left, a, label_a),
                (right, b, label_b),
            ]:
                with slot:
                    st.markdown(
                        "#### " + label
                    )

                    stats = calculate_kpis(data)

                    for name in c["kpis"]:
                        st.metric(
                            name,
                            stats[name],
                        )

        associated = {
            "Total de tarefas",
            "Preventivas",
            "Corretivas",
            "% Corretivas",
            "Máquinas atendidas",
        }

        if "Volume A × B" in c["selected"]:
            registry(
                c,
                "Volume A × B",
                comparison_bars(
                    a,
                    b,
                    label_a,
                    label_b,
                ),
                associated,
            )

        if "Evolução A × B" in c["selected"]:
            granularity = widget(
                "selectbox",
                "Agrupamento da comparação",
                c["key"] + "compare_gran",
                options=[
                    "Diária",
                    "Semanal",
                    "Mensal",
                ],
            )

            registry(
                c,
                "Evolução A × B",
                comparison_evolution(
                    a,
                    b,
                    label_a,
                    label_b,
                    c["spec"]["period"],
                    granularity,
                ),
                associated,
            )

        if "Participação A × B" in c["selected"]:
            registry(
                c,
                "Participação A × B",
                comparison_share(
                    a,
                    b,
                    label_a,
                    label_b,
                ),
                associated,
            )

        for name, column in [
            ("Problemas A × B", "Problema"),
            ("Peças A × B", "Peça"),
        ]:
            if name not in c["selected"]:
                continue

            total_categories = len(
                set(
                    category_counts(
                        a,
                        column,
                    ).index
                )
                | set(
                    category_counts(
                        b,
                        column,
                    ).index
                )
            )

            if not total_categories:
                st.info(
                    "Sem ocorrências válidas para "
                    + name
                    + "."
                )
                continue

            key = chart_key(c, name)

            with st.expander(
                "Top N — " + name
            ):
                own = widget(
                    "checkbox",
                    "Usar Top N individual",
                    key + "own",
                    value=False,
                )

                if own:
                    n = widget(
                        "number_input",
                        "Top N individual",
                        key + "n",
                        min_value=1,
                        max_value=total_categories,
                        value=min(
                            10,
                            total_categories,
                        ),
                        step=1,
                    )
                else:
                    n = c["top"]

            registry(
                c,
                name,
                comparison_occurrences(
                    a,
                    b,
                    column,
                    label_a,
                    label_b,
                    int(n),
                ),
                {
                    "Corretivas",
                    (
                        "Problema mais frequente"
                        if column == "Problema"
                        else "Peça mais trocada"
                    ),
                },
            )

    finish(c)
