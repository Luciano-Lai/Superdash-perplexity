import pandas as pd
import streamlit as st
import datetime

URL_ABA_MASTER = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vQhMjvBLcrdrgNIqCsHZOd3ZUb63abkzKPYYfOU7qFb45ljZmO2_UmerQjWWWxNvR4RfW_XElnCgHXf/"
    "pub?gid=1187149031&single=true&output=csv"
)

URL_ABA_DADOS = (
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vQhMjvBLcrdrgNIqCsHZOd3ZUb63abkzKPYYfOU7qFb45ljZmO2_UmerQjWWWxNvR4RfW_XElnCgHXf/"
    "pub?gid=152468513&single=true&output=csv"
)

MASTER_HEADER_KEYWORDS = [
    "código ar verificado",
    "codigo ar verificado",
    "técnico",
    "tecnico",
    "manutenção",
    "manutencao",
]

DADOS_HEADER_KEYWORDS = [
    "código ar verificado",
    "codigo ar verificado",
    "equipamento",
    "tipo",
]


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
        f"Não foi possível ler a planilha. Erro: {last_error}"
    )


def _find_header_row(df_raw, required_keywords):
    for index, row in df_raw.iterrows():
        values = [
            str(value).strip().lower()
            for value in row.values
            if pd.notna(value)
        ]

        matches = sum(
            1
            for keyword in required_keywords
            if any(keyword in value for value in values)
        )

        if matches >= len(required_keywords) - 1:
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

    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    df = df.loc[:, ~df.columns.str.lower().isin(["none", "nan", ""])]

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

    return _extract_table(df_raw, header_index)


def _normalize_column_names(df):
    rename_map = {}

    for column in df.columns:
        column_clean = str(column).strip().lower()

        if "código ar" in column_clean or "codigo ar" in column_clean:
            rename_map[column] = "Código Ar Verificado"

        elif "técnico" in column_clean or "tecnico" in column_clean:
            rename_map[column] = "Técnico"

        elif "manutenção" in column_clean or "manutencao" in column_clean:
            rename_map[column] = "Manutenção"

        elif column_clean == "data":
            rename_map[column] = "Data"

        elif "data garantia" in column_clean:
            rename_map[column] = "Data Garantia"

        elif "problema" in column_clean:
            rename_map[column] = "Problemas Relatados"

        elif "peça" in column_clean or "peca" in column_clean:
            rename_map[column] = "Peças Trocadas"

        elif "tarefa" in column_clean and "data" not in column_clean:
            rename_map[column] = "Tarefa"

    return df.rename(columns=rename_map)


def _split_multiple_values(value):
    if pd.isna(value):
        return []

    text = str(value).strip()

    if not text:
        return []

    parts = (
        text
        .replace("\n", ";")
        .split(";")
    )

    return [
        item.strip()
        for item in parts
        if item.strip()
    ]


def _calculate_guarantee_status(row):
    warranty_date = row.get("Data Garantia")

    if pd.isna(warranty_date):
        return "Não informado"

    today = pd.Timestamp(datetime.date.today())

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

    # ------------------------------------------------------------------
    # Junção entre tarefas e máquinas
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Padronização dos campos principais
    # ------------------------------------------------------------------
    df = df.rename(
        columns={
            "Data": "Data da tarefa",
            "Manutenção": "Tipo",
            machine_code: "Máquina",
        }
    )

    # Remove registros sem máquina
    if "Máquina" in df.columns:
        df = df[
            df["Máquina"]
            .notna()
            & (df["Máquina"].astype(str).str.strip() != "")
        ]

    # ------------------------------------------------------------------
    # Datas
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Garantia
    # ------------------------------------------------------------------
    df["Garantia"] = df.apply(
        _calculate_guarantee_status,
        axis=1,
    )

    # ------------------------------------------------------------------
    # Campos complementares
    # ------------------------------------------------------------------
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

    if "Peças Trocadas" in df.columns:
        df["Problema"] = df["Problemas Relatados"]
        df["Peça"] = df["Peças Trocadas"]
    else:
        df["Problema"] = df["Problemas Relatados"]
        df["Peça"] = pd.NA

    # ------------------------------------------------------------------
    # Normalização final
    # ------------------------------------------------------------------
    df["Tipo"] = (
        df["Tipo"]
        .astype(str)
        .str.strip()
        .str.title()
    )

    df["Máquina"] = df["Máquina"].astype(str).str.strip()
    df["Técnico"] = df["Técnico"].astype(str).str.strip()

    for column in [
        "Cliente",
        "Cidade",
        "Região",
        "Estado",
    ]:
        df[column] = df[column].astype(str).str.strip()

    df["Problema"] = df["Problema"].fillna("Não informado")
    df["Peça"] = df["Peça"].fillna("Nenhuma")

    return df
