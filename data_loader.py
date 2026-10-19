import unicodedata
from datetime import datetime

import pandas as pd
import streamlit as st

URL_ABA_MASTER = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vQhMjvBLcrdrgNIqCsHZOd3ZUb63abkzKPYYfOU7qFb45ljZmO2_UmerQjWWWxNvR4RfW_XElnCgHXf/"
    "pub?gid=1187149031&single=true&output=csv"
)

URL_ABA_DADOS = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vQhMjvBLcrdrgNIqCsHZOd3ZUb63abkzKPYYfOU7qFb45ljZmO2_UmerQjWWWxNvR4RfW_XElnCgHXf/"
    "pub?gid=152468513&single=true&output=csv"
)

MASTER_HEADER_KEYWORDS = [
    "código ar verificado",
    "técnico",
    "manutenção",
]

DADOS_HEADER_KEYWORDS = [
    "código ar verificado",
    "equipamento",
    "tipo",
]


def _normalize_text(value):
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


def _read_csv_with_fallback(url):
    last_error = None

    for encoding in ["utf-8-sig", "latin1", "cp1252"]:
        try:
            return pd.read_csv(
                url,
                header=None,
                encoding=encoding,
                dtype=str,
                keep_default_na=False,
                on_bad_lines="skip",
            )
        except Exception as error:
            last_error = error
            continue

    raise RuntimeError(
        f"Não foi possível ler a planilha. Detalhe: {last_error}"
    )


def _find_header_row(df_raw, required_keywords):
    normalized_keywords = [
        _normalize_text(keyword)
        for keyword in required_keywords
    ]

    for index, row in df_raw.iterrows():
        row_values = [
            _normalize_text(value)
            for value in row.values
            if pd.notna(value)
        ]

        matches = sum(
            1
            for keyword in normalized_keywords
            if any(
                keyword in value
                for value in row_values
            )
        )

        if matches >= 2:
            return index

    return None


def _extract_table(df_raw, header_index):
    columns = (
        df_raw.iloc[header_index]
        .astype(str)
        .str.strip()
        .tolist()
    )

    df = df_raw.iloc[header_index + 1:].copy()
    df.columns = columns

    df = df.loc[
        :,
        ~df.columns.str.startswith("Unnamed"),
    ]

    df = df.loc[
        :,
        ~df.columns.str.lower().isin([
            "none",
            "nan",
            "",
        ]),
    ]

    df = df.dropna(how="all")
    df = df.reset_index(drop=True)

    return df


def _load_sheet(url, required_keywords):
    df_raw = _read_csv_with_fallback(url)

    header_index = _find_header_row(
        df_raw,
        required_keywords,
    )

    if header_index is None:
        raise ValueError(
            "Não foi possível localizar a linha de cabeçalho da planilha."
        )

    return _extract_table(
        df_raw,
        header_index,
    )


def _normalize_column_names(df):
    rename_map = {}

    for column in df.columns:
        column_normalized = _normalize_text(column)

        if "codigo ar verificado" in column_normalized:
            rename_map[column] = "Código Ar Verificado"

        elif "tecnico" in column_normalized:
            rename_map[column] = "Técnico"

        elif "manutencao" in column_normalized:
            rename_map[column] = "Manutenção"

        elif column_normalized == "data":
            rename_map[column] = "Data"

        elif "data garantia" in column_normalized:
            rename_map[column] = "Data Garantia"

        elif "problema" in column_normalized:
            rename_map[column] = "Problemas Relatados"

        elif "peca" in column_normalized:
            rename_map[column] = "Peças Trocadas"

        elif "tarefa" in column_normalized and "data" not in column_normalized:
            rename_map[column] = "Tarefa"

    return df.rename(columns=rename_map)


def _calculate_guarantee_status(row):
    warranty_date = row.get("Data Garantia")

    if pd.isna(warranty_date):
        return "Não informado"

    today = pd.Timestamp.now().normalize()

    if warranty_date >= today:
        return "Dentro"

    return "Fora"
    

@st.cache_data(ttl=300)
def load_and_normalize_data():
    try:
        df_master = _load_sheet(
            URL_ABA_MASTER,
            MASTER_HEADER_KEYWORDS,
        )
    except Exception as error:
        st.error(
            "Não foi possível carregar a aba **Master**. "
            f"Detalhe técnico: {error}"
        )
        return pd.DataFrame()

    try:
        df_dados = _load_sheet(
            URL_ABA_DADOS,
            DADOS_HEADER_KEYWORDS,
        )
    except Exception as error:
        st.warning(
            "Não foi possível carregar a aba **Dados**. "
            f"Detalhe técnico: {error}"
        )
        df_dados = pd.DataFrame()

    df_master = _normalize_column_names(df_master)
    df_dados = _normalize_column_names(df_dados)

    machine_code = "Código Ar Verificado"

    if (
        not df_dados.empty
        and machine_code in df_dados.columns
        and machine_code in df_master.columns
    ):
        df = pd.merge(
            df_master,
            df_dados,
            on=machine_code,
            how="left",
        )
    else:
        df = df_master.copy()

    df = df.loc[:, ~df.columns.duplicated()]
    df = df.reset_index(drop=True)

    df = df.rename(
        columns={
            "Data": "Data da tarefa",
            "Manutenção": "Tipo",
            machine_code: "Máquina",
        }
    )

    if "Máquina" in df.columns:
        df = df[
            df["Máquina"].notna()
            & (
                df["Máquina"].astype(str).str.strip()
                != ""
            )
        ]

    if "Data da tarefa" in df.columns:
        df["Data da tarefa"] = pd.to_datetime(
            df["Data da tarefa"],
            errors="coerce",
            dayfirst=True,
        )
    else:
        df["Data da tarefa"] = pd.NaT

    if "Data Garantia" in df.columns:
        df["Data Garantia"] = pd.to_datetime(
            df["Data Garantia"],
            errors="coerce",
            dayfirst=True,
        )
    else:
        df["Data Garantia"] = pd.NaT

    df["Garantia"] = df.apply(
        _calculate_guarantee_status,
        axis=1,
    )

    optional_columns = [
        "Equipamento",
        "Tipo Equipamento",
        "Cidade",
        "Estado",
        "Cliente",
        "Região",
        "Técnico",
        "Tarefa",
        "Observações",
        "Observação Interna",
    ]

    for column in optional_columns:
        if column not in df.columns:
            df[column] = pd.NA

    if "Problemas Relatados" not in df.columns:
        df["Problemas Relatados"] = pd.NA

    df["Problema"] = df["Problemas Relatados"]

    if "Peças Trocadas" in df.columns:
        df["Peça"] = df["Peças Trocadas"]
    else:
        df["Peça"] = pd.NA

    def _clean_text(value):
    if pd.isna(value):
        return ""

    return str(value).strip()


df["Tipo"] = (
    df["Tipo"]
    .apply(_clean_text)
    .str.title()
)

df["Máquina"] = df["Máquina"].apply(_clean_text)
df["Técnico"] = df["Técnico"].apply(_clean_text)

for column in [
    "Cliente",
    "Cidade",
    "Região",
    "Estado",
]:
    df[column] = df[column].apply(_clean_text)
    
    df["Problema"] = df["Problema"].fillna("Não informado")
    df["Peça"] = df["Peça"].fillna("Nenhuma")

    return df
