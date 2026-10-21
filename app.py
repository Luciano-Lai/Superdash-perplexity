import streamlit as st
import pandas as pd
import plotly.express as px

# Importações dos módulos nativos do SuperDash
from data_loader import load_and_normalize_data
from filters import render_sidebar_filters
from kpis import calculate_executive_kpis

# 1. Configuração da página e aplicação de estilo executivo no topo
st.set_page_config(
    page_title="Painel Executivo de Manutenção",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Injeção do CSS exclusivo para a Primeira Parte (Header e Cards Executivos)
st.markdown("""
    <style>
        /* Cabeçalho Executivo em tom Navy */
        .exec-header-container {
            background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
            padding: 24px 32px;
            border-radius: 14px;
            color: #FFFFFF;
            margin-bottom: 24px;
            box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.15);
        }
        .exec-header-title {
            font-size: 26px;
            font-weight: 800;
            letter-spacing: -0.5px;
            margin: 0;
            color: #FFFFFF;
        }
        .exec-header-subtitle {
            font-size: 14px;
            color: #94A3B8;
            margin-top: 4px;
        }
        
        /* Cards Executivos com Bordas e Sombras */
        .kpi-card {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 18px 22px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03);
            margin-bottom: 12px;
        }
        .kpi-border-primary { border-left: 5px solid #0284C7; }
        .kpi-border-success { border-left: 5px solid #16A34A; }
        .kpi-border-warning { border-left: 5px solid #F59E0B; }
        .kpi-border-danger  { border-left: 5px solid #DC2626; }
        
        .kpi-label {
            font-size: 12px;
            font-weight: 700;
            color: #64748B;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            margin-bottom: 6px;
        }
        .kpi-value {
            font-size: 30px;
            font-weight: 800;
            color: #0F172A;
            line-height: 1;
        }
        .kpi-footer {
            font-size: 12px;
            color: #64748B;
            margin-top: 8px;
        }

        /* Abas Estilizadas */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: #F1F5F9;
            padding: 6px;
            border-radius: 10px;
        }
        .stTabs [aria-selected="true"] {
            background-color: #FFFFFF !important;
            color: #0284C7 !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
    </style>
""", unsafe_allow_html=True)

# 3. Carregamento resiliente dos dados
df_raw = load_and_normalize_data()

if df_raw.empty:
    st.error("⚠️ Não foi possível carregar os dados. Verifique a conexão com o Google Sheets.")
    st.stop()

# 4. Filtros da Barra Lateral
df_filtered, is_date_valid, has_additional_filter = render_sidebar_filters(df_raw)

# --- PRIMEIRA PARTE: CABEÇALHO E CARDS EXECUTIVOS ---

st.markdown("""
    <div class="exec-header-container">
        <div class="exec-header-title">🏢 Executive Operations Dashboard</div>
        <div class="exec-header-subtitle">Visão consolidada do parque de refrigeração, eficiência de manutenção e cobertura de garantias</div>
    </div>
""", unsafe_allow_html=True)

# Cálculo dos KPIs Globais
kpis = calculate_executive_kpis(df_filtered)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
        <div class="kpi-card kpi-border-primary">
            <div class="kpi-label">Volume de Atendimentos</div>
            <div class="kpi-value">{kpis['total_chamados']:,}</div>
            <div class="kpi-footer">📋 Registros no período</div>
        </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
        <div class="kpi-card kpi-border-success">
            <div class="kpi-label">Manutenções Preventivas</div>
            <div class="kpi-value">{kpis['preventivas']:,}</div>
            <div class="kpi-footer">🟢 {kpis['pct_preventivas']:.1f}% das operações</div>
        </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
        <div class="kpi-card kpi-border-warning">
            <div class="kpi-label">Atendimentos Corretivos</div>
            <div class="kpi-value">{kpis['corretivas']:,}</div>
            <div class="kpi-footer">🟠 Intervenções imediatas</div>
        </div>
    """, unsafe_allow_html=True)

with c4:
    variant_gar = "kpi-border-success" if kpis['pct_garantia'] >= 30 else "kpi-border-danger"
    st.markdown(f"""
        <div class="kpi-card {variant_gar}">
            <div class="kpi-label">Equipamentos em Garantia</div>
            <div class="kpi-value">{kpis['pct_garantia']:.1f}%</div>
            <div class="kpi-footer">🛡️ {kpis['garantia_qtd']} ativo(s) cobertos</div>
        </div>
    """, unsafe_allow_html=True)

st.write("")

# --- SEGUNDA PARTE: RESTANTE DO APLICATIVO ORGANIZADO POR ABAS ---

tab1, tab2, tab3 = st.tabs([
    "📈 Visão Estratégica & Performance", 
    "🛠️ Análise Técnica de Ativos", 
    "📑 Relatório Operacional & Exportação"
])

with tab1:
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("Proporção: Preventivas vs. Corretivas")
        if "Tipo" in df_filtered.columns and not df_filtered.empty:
            df_tipo = df_filtered["Tipo"].value_counts().reset_index()
            df_tipo.columns = ["Tipo", "Quantidade"]
            fig_pie = px.pie(
                df_tipo, 
                names="Tipo", 
                values="Quantidade", 
                hole=0.4,
                color_discrete_sequence=["#0284C7", "#F59E0B", "#16A34A", "#DC2626"]
            )
            fig_pie.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=340)
            st.plotly_chart(fig_pie, use_container_width=True)

    with col_chart2:
        st.subheader("Top 5 Problemas Relatados")
        if "Problema" in df_filtered.columns and not df_filtered.empty:
            df_prob = df_filtered["Problema"].value_counts().head(5).reset_index()
            df_prob.columns = ["Problema", "Quantidade"]
            fig_bar = px.bar(
                df_prob, 
                x="Quantidade", 
                y="Problema", 
                orientation="h",
                color_discrete_sequence=["#0284C7"]
            )
            fig_bar.update_layout(yaxis=dict(autorange="reversed"), margin=dict(t=20, b=20, l=20, r=20), height=340)
            st.plotly_chart(fig_bar, use_container_width=True)

with tab2:
    col_t1, col_t2 = st.columns(2)
    
    with col_t1:
        st.subheader("Atendimentos por Técnico")
        if "Técnico" in df_filtered.columns and not df_filtered.empty:
            df_tech = df_filtered["Técnico"].value_counts().reset_index()
            df_tech.columns = ["Técnico", "Atendimentos"]
            fig_tech = px.bar(
                df_tech, 
                x="Técnico", 
                y="Atendimentos",
                color_discrete_sequence=["#0F172A"]
            )
            fig_tech.update_layout(height=340, margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig_tech, use_container_width=True)

    with col_t2:
        st.subheader("Status de Garantia")
        if "Garantia" in df_filtered.columns and not df_filtered.empty:
            df_gar = df_filtered["Garantia"].value_counts().reset_index()
            df_gar.columns = ["Status", "Quantidade"]
            fig_gar = px.bar(
                df_gar, 
                x="Status", 
                y="Quantidade",
                color="Status",
                color_discrete_map={"Dentro": "#16A34A", "Fora": "#DC2626", "Não informado": "#94A3B8"}
            )
            fig_gar.update_layout(height=340, margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig_gar, use_container_width=True)

with tab3:
    st.subheader("Tabela de Registros Filtrados")
    st.dataframe(df_filtered, use_container_width=True, hide_index=True)