import pandas as pd
import streamlit as st

COLUMNS = ["Máquina", "Técnico", "Cliente", "Estado", "Região", "Cidade"]


def reset_dashboard():
    for key in list(st.session_state):
        if key.startswith("dash_"):
            del st.session_state[key]


def apply_filters(df, spec, ignore=()):
    result = df.copy()
    period = spec.get("period", ())
    if len(period) != 2:
        return result.iloc[0:0]
    start, end = map(pd.Timestamp, period)
    result = result.loc[result["Data da tarefa"].ge(start) & result["Data da tarefa"].lt(end + pd.Timedelta(days=1))]
    if "Tipo" not in ignore and spec.get("Tipo", "Todas") != "Todas":
        result = result.loc[result["Tipo"].eq(spec["Tipo"])]
    for column in COLUMNS:
        if column not in ignore and spec.get(column):
            result = result.loc[result[column].isin(spec[column])]
    return result.copy()


def render_sidebar_filters(df):
    with st.sidebar:
        st.header("Filtros")
        st.caption("Período + pelo menos um filtro adicional.")
        st.button("Limpar filtros e seleções", on_click=reset_dashboard, use_container_width=True)
        if st.button("Atualizar dados", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        valid = df["Data da tarefa"].dropna()
        if valid.empty:
            st.error("Não há datas válidas na base.")
            return df.iloc[0:0], False, False, {}
        period = st.date_input("Período", value=(valid.min().date(), valid.max().date()),
                               min_value=valid.min().date(), max_value=valid.max().date(),
                               format="DD/MM/YYYY", key="dash_period")
        spec = {"period": period}
        spec["Tipo"] = st.selectbox("Tipo de manutenção", ["Todas", "Preventiva", "Corretiva"], key="dash_type")
        labels = dict(zip(df["Máquina"], df["Seleção da máquina"]))
        for column in COLUMNS:
            options = sorted(v for v in df[column].dropna().unique() if str(v).strip())
            if not options:
                spec[column] = []
                st.caption(f"{column}: sem cadastro na fonte.")
                continue
            kwargs = {"format_func": lambda code: labels.get(code, code)} if column == "Máquina" else {}
            spec[column] = st.multiselect(column, options, key=f"dash_filter_{column}", **kwargs)
    valid_period = isinstance(period, (tuple, list)) and len(period) == 2 and period[0] <= period[1]
    additional = spec["Tipo"] != "Todas" or any(spec.get(c) for c in COLUMNS)
    return apply_filters(df, spec), valid_period, additional, spec
