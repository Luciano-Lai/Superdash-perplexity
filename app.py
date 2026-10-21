import streamlit as st
from data_loader import load_and_normalize_data
from filters import render_sidebar_filters
from ui import apply_theme

st.set_page_config(page_title="Painel de Refrigeração", page_icon="❄️", layout="wide", initial_sidebar_state="expanded")
apply_theme()

pages = [
    st.Page("views/monitoramento.py", title="Monitoramento", icon="📊", default=True),
    st.Page("views/analise_tarefas.py", title="Análise de tarefas", icon="🧾"),
    st.Page("views/maquinas.py", title="Máquinas", icon="❄️"),
    st.Page("views/corretivas.py", title="Corretivas", icon="🔧"),
    st.Page("views/clientes_regioes.py", title="Clientes e regiões", icon="🏢"),
]
page = st.navigation(pages, position="top")

try:
    raw = load_and_normalize_data()
except Exception as error:
    st.error("Não foi possível carregar os dados. Nenhum resultado parcial será apresentado.")
    with st.expander("Diagnóstico da leitura"):
        st.code(str(error))
    st.stop()

if raw.empty:
    st.info("A base não contém tarefas disponíveis.")
    st.stop()

# Widgets comuns no ponto de entrada: permanecem ao navegar entre páginas.
cut, valid, additional, spec = render_sidebar_filters(raw)
st.session_state["_page_context"] = dict(raw=raw, cut=cut, valid=valid, additional=additional, spec=spec)
page.run()
