import unicodedata

import pandas as pd
import streamlit as st


COLUMNS = [
    "Máquina",
    "Técnico",
    "Cliente",
    "Estado",
    "Região",
    "Cidade",
]


def alphabetical_key(value):
    text = unicodedata.normalize(
        "NFKD",
        str(value).strip().casefold(),
    )

    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )

    return " ".join(text.split())


def reset_dashboard():
    for key in list(st.session_state):
        if key.startswith("dash_"):
            del st.session_state[key]


def apply_filters(df, spec, ignore=()):
    result = df.copy()

    period = spec.get("period", ())

    if len(period) != 2:
        return result.iloc[0:0].copy()

    start, end = map(
        pd.Timestamp,
        period,
    )

    result = result.loc[
        result["Data da tarefa"].ge(start)
        & result["Data da tarefa"].lt(
            end + pd.Timedelta(days=1)
        )
    ]

    selected_type = spec.get(
        "Tipo",
        "Todas",
    )

    if (
        "Tipo" not in ignore
        and selected_type != "Todas"
    ):
        result = result.loc[
            result["Tipo"].eq(selected_type)
        ]

    for column in COLUMNS:
        if column in ignore:
            continue

        selected = spec.get(column)

        if selected:
            result = result.loc[
                result[column].isin(selected)
            ]

    return result.copy()


def render_sidebar_filters(df):
    with st.sidebar:
        st.header("Filtros")

        st.caption(
            "Período + pelo menos um filtro adicional."
        )

        st.button(
            "Limpar filtros e seleções",
            on_click=reset_dashboard,
            use_container_width=True,
        )

        if st.button(
            "Atualizar dados",
            use_container_width=True,
        ):
            st.cache_data.clear()
            st.rerun()

        valid_dates = (
            df["Data da tarefa"]
            .dropna()
        )

        if valid_dates.empty:
            st.error(
                "Não há datas válidas na base."
            )

            return (
                df.iloc[0:0].copy(),
                False,
                False,
                {},
            )

        period = st.date_input(
            "Período",
            value=(
                valid_dates.min().date(),
                valid_dates.max().date(),
            ),
            min_value=valid_dates.min().date(),
            max_value=valid_dates.max().date(),
            format="DD/MM/YYYY",
            key="dash_period",
        )

        spec = {
            "period": period,
        }

        spec["Tipo"] = st.selectbox(
            "Tipo de manutenção",
            [
                "Todas",
                "Preventiva",
                "Corretiva",
            ],
            key="dash_type",
        )

        labels = dict(
            zip(
                df["Máquina"],
                df["Seleção da máquina"],
            )
        )

        for column in COLUMNS:
            options = [
                value
                for value in df[column].dropna().unique()
                if str(value).strip()
            ]

            if column == "Máquina":
                options = sorted(
                    options,
                    key=lambda code: (
                        alphabetical_key(
                            labels.get(code, code)
                        ),
                        alphabetical_key(code),
                    ),
                )
            else:
                options = sorted(
                    options,
                    key=alphabetical_key,
                )

            if not options:
                spec[column] = []

                st.caption(
                    f"{column}: sem cadastro na fonte."
                )
                continue

            kwargs = {}

            if column == "Máquina":
                kwargs["format_func"] = (
                    lambda code: labels.get(code, code)
                )

            spec[column] = st.multiselect(
                column,
                options,
                key=f"dash_filter_{column}",
                **kwargs,
            )

    valid_period = (
        isinstance(period, (tuple, list))
        and len(period) == 2
        and period[0] <= period[1]
    )

    additional = (
        spec["Tipo"] != "Todas"
        or any(
            spec.get(column)
            for column in COLUMNS
        )
    )

    if valid_period:
        cut = apply_filters(
            df,
            spec,
        )
    else:
        cut = df.iloc[0:0].copy()

    return (
        cut,
        valid_period,
        additional,
        spec,
    )
