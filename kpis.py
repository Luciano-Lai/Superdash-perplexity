from html import escape
import pandas as pd
import streamlit as st
from data_loader import clean, norm

INVALID = {"", "nenhuma", "nenhum", "nao informado", "nan", "none", "<na>"}


def occurrence_frame(df, column):
    out = df.loc[df["Tipo"].eq("Corretiva")].copy()
    out[column] = out[column].map(lambda v: clean(v).replace("\n", ";").split(";"))
    out = out.explode(column)
    out[column] = out[column].map(clean)
    return out.loc[~out[column].map(norm).isin(INVALID)].copy()


def calculate_kpis(df):
    total = len(df)
    prev = int(df["Tipo"].eq("Preventiva").sum())
    corr = df.loc[df["Tipo"].eq("Corretiva")]
    def frequent(column):
        counts = occurrence_frame(df, column)[column].value_counts()
        return str(counts.index[0]) if not counts.empty else "—"
    return {
        "Total de tarefas": total, "Preventivas": prev, "Corretivas": len(corr),
        "% Preventivas": f"{prev / total * 100:.1f}%".replace(".", ",") if total else "—",
        "% Corretivas": f"{len(corr) / total * 100:.1f}%".replace(".", ",") if total else "—",
        "Máquinas atendidas": df.loc[df["Máquina"].ne(""), "Máquina"].nunique(),
        "Técnicos envolvidos": df.loc[df["Técnico"].ne(""), "Técnico"].nunique(),
        "Corretivas em garantia": int(corr["Garantia"].eq("Dentro").sum()),
        "Corretivas fora da garantia": int(corr["Garantia"].eq("Fora").sum()),
        "Problema mais frequente": frequent("Problema"), "Peça mais trocada": frequent("Peça"),
    }


def render_kpi_cards(selected_kpis, values):
    for start in range(0, len(selected_kpis), 4):
        group = selected_kpis[start:start + 4]
        columns = st.columns(4)
        for col, name in zip(columns, group):
            value = values.get(name, "—")
            is_text = name in {"Problema mais frequente", "Peça mais trocada"}
            display = f"{int(value):,}".replace(",", ".") if isinstance(value, (int, float)) else str(value)
            size = "1rem" if is_text else "2rem"
            html = (f'<div class="kpi-card"><div class="kpi-label">{escape(name)}</div>'
                    f'<div class="kpi-value" style="font-size:{size}">{escape(display)}</div></div>')
            col.markdown(html, unsafe_allow_html=True)
