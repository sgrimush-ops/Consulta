#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dashboard Online - Streamlit
Versão portável para rodar em qualquer servidor online
Importa sugestao_ia.parquet e reproduz o dashboard completo
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import os
from pathlib import Path
from sqlalchemy import create_engine, text

# =========================================================
# CONFIGURAÇÕES
# =========================================================
BASE_DATA_PATH = os.environ.get("RENDER_DISK_PATH", "data")
os.makedirs(BASE_DATA_PATH, exist_ok=True)


def setup_css():
    st.markdown("""
    <style>
        .metric-box {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
    </style>
    """, unsafe_allow_html=True)


# =========================================================
# CARREGAMENTO DE DADOS
# =========================================================
@st.cache_data
def carregar_dados_parquet(base_path):
    """Carrega dados do sugestao_ia.parquet do diretório de dados"""
    arquivo = os.path.join(base_path, 'sugestao_ia.parquet')

    if not os.path.exists(arquivo):
        st.error(f"❌ Arquivo não encontrado: {arquivo}")
        return None

    try:
        df = pd.read_parquet(arquivo)
        st.success(f"✓ Dados carregados: {len(df)} linhas")
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar: {e}")
        return None


@st.cache_data
def carregar_dados_banco(_engine):
    """Carrega dados da tabela sugestao_ia do banco de dados"""
    try:
        with _engine.connect() as conn:
            df = pd.read_sql_table('sugestao_ia', con=conn)
            st.success(f"✓ Dados carregados do banco: {len(df)} linhas")
            return df
    except Exception as e:
        st.warning(f"⚠️ Não foi possível carregar do banco: {e}")
        return None


# =========================================================
# CÁLCULO DE MÉTRICAS
# =========================================================
def calcular_metricas(df):
    """Calcula métricas do dashboard"""
    metricas = {}

    metricas['total_analisados'] = len(df)

    # Sugestões
    if 'sugestao_caixa' in df.columns and 'sugestao_pendente' in df.columns:
        df['sugestao_total'] = df['sugestao_caixa'].fillna(
            0) + df['sugestao_pendente'].fillna(0)
        metricas['com_sugestao'] = (df['sugestao_total'] > 0).sum()
        metricas['sem_sugestao'] = (df['sugestao_total'] == 0).sum()
        metricas['perc_sugestao'] = (
            metricas['com_sugestao'] / metricas['total_analisados'] * 100) if metricas['total_analisados'] > 0 else 0
    else:
        metricas['com_sugestao'] = (df['sugestao'] > 0).sum()
        metricas['sem_sugestao'] = (df['sugestao'] == 0).sum()
        metricas['perc_sugestao'] = (
            metricas['com_sugestao'] / metricas['total_analisados'] * 100) if metricas['total_analisados'] > 0 else 0

    # Situações
    if 'situacao' in df.columns:
        situacoes = df['situacao'].value_counts()
        metricas['falta_estoque'] = situacoes.get('falta de estoque', 0)
        metricas['insuficiente'] = situacoes.get('insuficiente', 0)
        metricas['em_atendimento'] = situacoes.get('em atendimento', 0)
        metricas['aguardando_giro'] = situacoes.get('aguardando_giro', 0)
    else:
        metricas['falta_estoque'] = 0
        metricas['insuficiente'] = 0
        metricas['em_atendimento'] = 0
        metricas['aguardando_giro'] = 0

    # Comparativo Gerado vs Sugerido
    if 'gerado' in df.columns and 'sugestao' in df.columns:
        df_comp = df[df['sugestao'] > 0].copy()
        metricas['total_gerado'] = df_comp['gerado'].sum()
        metricas['total_sugerido'] = df_comp['sugestao'].sum()

        if metricas['total_gerado'] > 0:
            metricas['variacao_perc'] = (
                (metricas['total_sugerido'] - metricas['total_gerado']) /
                metricas['total_gerado'] * 100
            )
        else:
            metricas['variacao_perc'] = 0
    else:
        metricas['total_gerado'] = 0
        metricas['total_sugerido'] = df['sugestao'].sum(
        ) if 'sugestao' in df.columns else 0
        metricas['variacao_perc'] = 0

    # Giro CD
    if 'estoque_total_cd' in df.columns and 'sugestao' in df.columns:
        df_com_sugestao = df[df['sugestao'] > 0].copy()
        if len(df_com_sugestao) > 0:
            # Sugestão mensal total
            sugestao_mensal_total = df_com_sugestao['sugestao'].sum()
            estoque_total_cd = df_com_sugestao['estoque_total_cd'].sum()

            # Giro = Estoque / (Sugestão mensal / 30)
            # Resultado em dias de cobertura
            if sugestao_mensal_total > 0:
                metricas['giro_cd'] = (
                    estoque_total_cd / sugestao_mensal_total) * 30
            else:
                metricas['giro_cd'] = 0
        else:
            metricas['giro_cd'] = 0
    else:
        metricas['giro_cd'] = 0

    # Giro por loja
    metricas['giro_por_loja'] = {}
    if 'loja' in df.columns and 'estoque_total_loja' in df.columns and 'sugestao' in df.columns:
        for loja in df['loja'].unique():
            df_loja = df[(df['loja'] == loja) & (df['sugestao'] > 0)].copy()
            if len(df_loja) > 0:
                sugestao_mensal_loja = df_loja['sugestao'].sum()
                estoque_loja = df_loja['estoque_total_loja'].sum()

                # Giro por loja em dias
                if sugestao_mensal_loja > 0:
                    giro = (estoque_loja / sugestao_mensal_loja) * 30
                    metricas['giro_por_loja'][str(loja)] = giro

    if metricas['giro_por_loja']:
        metricas['giro_medio_geral'] = sum(
            metricas['giro_por_loja'].values()) / len(metricas['giro_por_loja'])
    else:
        metricas['giro_medio_geral'] = 0

    # Risco de ruptura
    if 'cobertura_dias' in df.columns:
        metricas['risco_ruptura_3d'] = (df['cobertura_dias'] < 3).sum()
        metricas['risco_ruptura_5d'] = (df['cobertura_dias'] < 5).sum()
    else:
        metricas['risco_ruptura_3d'] = 0
        metricas['risco_ruptura_5d'] = 0

    # Data da análise
    if 'data' in df.columns:
        metricas['data_analise'] = str(df['data'].iloc[0])
    else:
        metricas['data_analise'] = datetime.now().strftime('%Y-%m-%d')

    return metricas


# =========================================================
# GRÁFICOS
# =========================================================
def criar_grafico_sugestoes(metricas):
    """Cria gráfico de pizza de sugestões"""
    fig = go.Figure(data=[
        go.Pie(
            labels=[
                f"Com Sugestão ({metricas['com_sugestao']:,})",
                f"Sem Sugestão ({metricas['sem_sugestao']:,})"
            ],
            values=[metricas['com_sugestao'], metricas['sem_sugestao']],
            marker=dict(colors=['#2ecc71', '#95a5a6']),
            textposition='inside',
            textinfo='label+percent',
            insidetextorientation='horizontal'
        )
    ])
    fig.update_layout(height=400)
    return fig


def criar_grafico_situacoes(metricas):
    """Cria gráfico de pizza de situações"""
    fig = go.Figure(data=[
        go.Pie(
            labels=[
                f"Atendimento ({metricas['em_atendimento']})",
                f"Insuficiente ({metricas['insuficiente']})",
                f"Falta Estoque ({metricas['falta_estoque']})",
                f"Aguardando ({metricas['aguardando_giro']})"
            ],
            values=[
                metricas['em_atendimento'],
                metricas['insuficiente'],
                metricas['falta_estoque'],
                metricas['aguardando_giro']
            ],
            marker=dict(
                colors=['#2ecc71', '#f39c12', '#e74c3c', '#3498db']),
            textposition='inside',
            textinfo='label+percent',
            insidetextorientation='horizontal'
        )
    ])
    fig.update_layout(height=400)
    return fig


def criar_grafico_giro_lojas(metricas):
    """Cria gráfico de giro por loja"""
    if not metricas['giro_por_loja']:
        return None

    df_lojas = pd.DataFrame(
        list(metricas['giro_por_loja'].items()),
        columns=['Loja', 'Giro Médio (dias)']
    ).sort_values('Giro Médio (dias)', ascending=False).head(20)

    df_lojas['Loja_Label'] = 'Loja ' + df_lojas['Loja'].astype(str)

    def get_color_giro(valor):
        if valor < 22:
            return '#27ae60'
        elif valor <= 30:
            return '#f39c12'
        else:
            return '#e74c3c'

    df_lojas['Cor'] = df_lojas['Giro Médio (dias)'].apply(get_color_giro)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df_lojas['Loja_Label'],
        x=df_lojas['Giro Médio (dias)'],
        orientation='h',
        marker=dict(color=df_lojas['Cor']),
        text=df_lojas['Giro Médio (dias)'].round(1),
        textposition='outside'
    ))

    fig.add_vline(x=22, line_dash="dash", line_color="green",
                  annotation_text="Saudável (22d)", annotation_position="top right")
    fig.add_vline(x=30, line_dash="dash", line_color="red",
                  annotation_text="Alto (30d)", annotation_position="top right")

    fig.update_layout(
        title="Giro Médio por Loja (Top 20)",
        xaxis_title="Dias",
        yaxis_title="Loja",
        height=500,
        margin=dict(l=150, r=100, t=80, b=60)
    )

    return fig


# =========================================================
# PÁGINA PRINCIPAL
# =========================================================
def show_dashboard_online_page(engine, base_data_path=None):
    """Função principal da página dashboard"""
    setup_css()

    st.title("📊 Dashboard Sugestões IA")
    st.markdown("---")

    # Tentar carregar do banco automaticamente
    df = None

    if engine:
        with st.spinner("Carregando dados do banco..."):
            df = carregar_dados_banco(engine)

    # Se não conseguiu do banco, oferecer opção de arquivo local
    if df is None:
        st.info("ℹ️ Para carregar dados do arquivo local, use o formulário abaixo:")

        if base_data_path and st.button("Carregar do Arquivo Local", type="primary"):
            with st.spinner("Carregando arquivo local..."):
                df = carregar_dados_parquet(base_data_path)
        else:
            st.warning(
                "⚠️ Nenhum dado disponível. Configure o banco de dados ou um arquivo local.")
            st.stop()
    else:
        # Se carregou do banco com sucesso, mostrar opção de recarregar
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Recarregar do Banco", type="secondary"):
                st.cache_data.clear()
                st.rerun()
        with col2:
            if base_data_path and st.button("📁 Carregar do Arquivo Local", type="secondary"):
                with st.spinner("Carregando arquivo local..."):
                    df = carregar_dados_parquet(base_data_path)
                    if df is not None:
                        st.rerun()

    # Calcular métricas
    metricas = calcular_metricas(df)

    # --- DIAGNÓSTICO (Expandível) ---
    with st.expander("🔍 Diagnóstico da Estrutura de Dados"):
        diag = diagnosticar_estrutura(df)
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Colunas Disponíveis:**")
            for col in diag['colunas']:
                st.code(col, language="text")

        with col2:
            st.write("**Resumo dos Dados:**")
            st.write(f"- Total de linhas: {diag['total_linhas']}")
            st.write(
                f"- Colunas com null: {sum(1 for v in diag['nulos'].values() if v > 0)}")

        st.write("**Métricas Calculadas:**")
        st.json({
            'giro_cd_dias': round(metricas['giro_cd'], 2),
            'giro_por_loja_count': len(metricas['giro_por_loja']),
            'com_sugestao': metricas['com_sugestao'],
            'total_gerado': metricas['total_gerado'],
            'total_sugerido': metricas['total_sugerido']
        })

    st.markdown("---")

    # Header com info geral
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Produtos", f"{metricas['total_analisados']:,}")
    with col2:
        st.metric("Com Sugestão", f"{metricas['com_sugestao']:,}")
    with col3:
        st.metric("Data Análise", metricas['data_analise'])

    st.markdown("---")

    # SEÇÃO 1: SUGESTÕES
    st.header("📦 Sugestões ML")
    col1, col2 = st.columns(2)

    with col1:
        fig1 = criar_grafico_sugestoes(metricas)
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        fig2 = criar_grafico_situacoes(metricas)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # SEÇÃO 2: COMPARATIVO GERADO vs SUGERIDO
    st.header("📈 Comparativo: Gerado vs Sugerido")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Gerado", f"{metricas['total_gerado']:,} cx")
    with col2:
        st.metric("Total Sugerido", f"{metricas['total_sugerido']:,} cx")
    with col3:
        cor = "🟢" if metricas['variacao_perc'] < 0 else "🔴"
        st.metric("Variação", f"{metricas['variacao_perc']:+.2f}%", f"{cor}")

    st.markdown("---")

    # SEÇÃO 3: GIRO DO CD
    st.header("📦 Análise de Giro do CD")

    giro_cd = metricas['giro_cd']
    if giro_cd < 90:
        cor_giro = "#27ae60"
        status = "ÓTIMO"
        msg = "CD com giro saudável"
    elif giro_cd <= 120:
        cor_giro = "#f39c12"
        status = "ATENÇÃO"
        msg = "Giro acima do ideal"
    else:
        cor_giro = "#e74c3c"
        status = "CRÍTICO"
        msg = "CD girando muito lentamente"

    st.markdown(f"""
    <div style="background-color: {cor_giro}; color: white; padding: 20px; border-radius: 10px;">
        <h3 style="margin:0;">Dias de Cobertura do CD</h3>
        <h2 style="margin:10px 0;">{giro_cd:.1f} dias</h2>
        <p style="margin:0; font-size:14px;">{status}: {msg}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # SEÇÃO 4: GIRO POR LOJA
    st.header("🏪 Giro Médio por Loja")

    if metricas['giro_por_loja']:
        fig = criar_grafico_giro_lojas(metricas)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("ℹ️ Sem dados de giro por loja disponíveis")

    st.markdown("---")

    # SEÇÃO 5: RISCO DE RUPTURA
    st.header("⚠️ Risco de Ruptura")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Produtos com <3 dias", f"{metricas['risco_ruptura_3d']}")
    with col2:
        st.metric("Produtos com <5 dias", f"{metricas['risco_ruptura_5d']}")

    st.markdown("---")

    # RODAPÉ
    st.markdown(f"""
    <div style="text-align: center; color: #95a5a6; font-size: 12px;">
        Dashboard gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}
        <br>
        Dados: sugestao_ia.parquet
    </div>
    """, unsafe_allow_html=True)


# =========================================================
# EXECUÇÃO STANDALONE
# =========================================================
if __name__ == '__main__':
    st.set_page_config(
        page_title="Dashboard Sugestões IA",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Para uso standalone, criar engine dummy
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        engine = create_engine(db_url, connect_args={
                               "sslmode": "require"}, pool_size=10, max_overflow=5)
    else:
        engine = None

    show_dashboard_online_page(engine, BASE_DATA_PATH)
