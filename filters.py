import datetime

import pandas as pd
import streamlit as st

DATE_COLUMN = "Data da tarefa"


def _normalize_text(value):
    import unicodedata

    text = str(value).strip().lower()

    text = unicodedata.normalize(
        "NFKD",
        text,
    ).encode(
        "ascii",
        "ignore",
    ).decode(
        "ascii",
    )

    return text


def _get_unique_options(df, column):
    if column not in df.columns:
        return []

    options = (
        df[column]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
    )

    return sorted(options)


def _apply_multiselect_filter(df, column, selected_values):
    if not selected_values:
        return df

    return df[
        df[column]
        .astype(str)
        .str.strip()
        .isin(selected_values)
    ]


def render_sidebar_filters(df):
    if df.empty or DATE_COLUMN not in df.columns:
        st.sidebar.info(
            "Não foi possível carregar os dados da planilha."
        )

        return (
            pd.DataFrame(),
            False,
            False,
        )

    st.sidebar.markdown("### Filtros")
    st.sidebar.caption(
        "Selecione o período e pelo menos um filtro adicional."
    )

    dates = pd.to_datetime(
        df[DATE_COLUMN],
        errors="coerce",
        dayfirst=True,
    )

    valid_dates = dates.dropna()

    if not valid_dates.empty:
        min_date = valid_dates.min().date()
        max_date = valid_dates.max().date()
    else:
        min_date = datetime.date(2026, 1, 1)
        max_date = datetime.date(2026, 12, 31)

    date_range = st.sidebar.date_input(
        "Período",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    is_date_valid = (
        isinstance(date_range, (tuple, list))
        and len(date_range) == 2
    )

    st.sidebar.markdown("#### Tipo de tarefa")

    task_type = st.sidebar.selectbox(
        "Tipo",
        ["Todas", "Preventiva", "Corretiva"],
        label_visibility="collapsed",
    )

    st.sidebar.markdown("#### Máquina e atendimento")

    machine_options = _get_unique_options(df, "Máquina")
    technician_options = _get_unique_options(df, "Técnico")
    client_options = _get_unique_options(df, "Cliente")

    selected_machines = st.sidebar.multiselect(
        "Máquina",
        options=machine_options,
        placeholder="Selecione uma ou mais máquinas",
    )

    selected_technicians = st.sidebar.multiselect(
        "Técnico",
        options=technician_options,
        placeholder="Selecione um ou mais técnicos",
    )

    selected_clients = st.sidebar.multiselect(
        "Cliente",
        options=client_options,
        placeholder="Selecione um ou mais clientes",
    )

    st.sidebar.markdown("#### Localização")

    city_options = _get_unique_options(df, "Cidade")
    region_options = _get_unique_options(df, "Região")
    state_options = _get_unique_options(df, "Estado")

    selected_cities = st.sidebar.multiselect(
        "Cidade",
        options=city_options,
        placeholder="Selecione uma ou mais cidades",
    )

    selected_regions = st.sidebar.multiselect(
        "Região",
        options=region_options,
        placeholder="Selecione uma ou mais regiões",
    )

    selected_states = st.sidebar.multiselect(
        "Estado",
        options=state_options,
        placeholder="Selecione um ou mais estados",
    )

    st.sidebar.markdown("")

    if st.sidebar.button(
        "Limpar filtros",
        use_container_width=True,
        type="secondary",
    ):
        st.session_state.clear()
        st.rerun()

    has_additional_filter = any([
        task_type != "Todas",
        len(selected_machines) > 0,
        len(selected_technicians) > 0,
        len(selected_clients) > 0,
        len(selected_cities) > 0,
        len(selected_regions) > 0,
        len(selected_states) > 0,
    ])

    df_filtered = df.copy()

    if is_date_valid:
        start_date, end_date = date_range

        start_timestamp = pd.Timestamp(start_date)
        end_timestamp = pd.Timestamp(end_date).replace(
            hour=23,
            minute=59,
            second=59,
        )

        task_dates = pd.to_datetime(
            df_filtered[DATE_COLUMN],
            errors="coerce",
            dayfirst=True,
        )

        date_mask = (
            (task_dates >= start_timestamp)
            & (task_dates <= end_timestamp)
        )

        df_filtered = df_filtered[date_mask]

    if task_type != "Todas":
        df_filtered = df_filtered[
            df_filtered["Tipo"] == task_type
        ]

    df_filtered = _apply_multiselect_filter(
        df_filtered,
        "Máquina",
        selected_machines,
    )

    df_filtered = _apply_multiselect_filter(
        df_filtered,
        "Técnico",
        selected_technicians,
    )

    df_filtered = _apply_multiselect_filter(
        df_filtered,
        "Cliente",
        selected_clients,
    )

    df_filtered = _apply_multiselect_filter(
        df_filtered,
        "Cidade",
        selected_cities,
    )

    df_filtered = _apply_multiselect_filter(
        df_filtered,
        "Região",
        selected_regions,
    )

    df_filtered = _apply_multiselect_filter(
        df_filtered,
        "Estado",
        selected_states,
    )

    return (
        df_filtered,
        is_date_valid,
        has_additional_filter,
    )
