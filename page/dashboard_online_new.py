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

# CSS customizado


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

        # Em Atendimento = produtos com sugestão IA (caixas sugeridas + pendentes)
        if 'sugestao_caixa' in df.columns and 'sugestao_pendente' in df.columns:
            df_com_sugestao = df[(df['sugestao_caixa'].fillna(0) > 0) | (
                df['sugestao_pendente'].fillna(0) > 0)]
            metricas['em_atendimento'] = len(df_com_sugestao)
        else:
            metricas['em_atendimento'] = situacoes.get(
                'em atendimento', 0) + situacoes.get('enviar_pedido', 0)

        # Falta Estoque = tudo que foi pedido mas está em falta ou insuficiente no CD
        metricas['falta_estoque'] = situacoes.get(
            'falta de estoque', 0) + situacoes.get('falta_cd', 0)
        metricas['insuficiente'] = situacoes.get('insuficiente', 0)

        # Falta CD = falta_estoque + insuficiente (tudo que foi pedido mas não pode ser atendido)
        metricas['falta_cd_total'] = metricas['falta_estoque'] + \
            metricas['insuficiente']

        metricas['aguardando_giro'] = situacoes.get('aguardando_giro', 0)
    else:
        metricas['falta_estoque'] = 0
        metricas['insuficiente'] = 0
        metricas['em_atendimento'] = 0
        metricas['aguardando_giro'] = 0
        metricas['falta_cd_total'] = 0

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

    # Giro CD (corrigido)
    if 'estoque_total_cd' in df.columns and 'sugestao' in df.columns:
        df_com_sugestao = df[df['sugestao'] > 0].copy()
        if len(df_com_sugestao) > 0:
            sugestao_diaria = df_com_sugestao['sugestao'].sum() / 30
            estoque_total_cd = df_com_sugestao['estoque_total_cd'].sum()
            if sugestao_diaria > 0:
                metricas['giro_cd'] = estoque_total_cd / sugestao_diaria
            else:
                metricas['giro_cd'] = 0
        else:
            metricas['giro_cd'] = 0
    else:
        metricas['giro_cd'] = 0

    # Giro por loja
    metricas['giro_por_loja'] = {}
    if 'loja' in df.columns and 'estoque_total_loja' in df.columns:
        for loja in df['loja'].unique():
            df_loja = df[(df['loja'] == loja) & (df['sugestao'] > 0)].copy()
            if len(df_loja) > 0:
                sugestao_diaria_loja = df_loja['sugestao'].sum() / 30
                estoque_loja = df_loja['estoque_total_loja'].sum()
                if sugestao_diaria_loja > 0:
                    giro = estoque_loja / sugestao_diaria_loja
                    metricas['giro_por_loja'][str(loja)] = giro

    if metricas['giro_por_loja']:
        metricas['giro_medio_geral'] = sum(
            metricas['giro_por_loja'].values()) / len(metricas['giro_por_loja'])
    else:
        metricas['giro_medio_geral'] = 0

    # Risco de ruptura
    if 'cobertura_dias' in df.columns:
        metricas['risco_ruptura_3d'] = (df['cobertura_dias'] < 3).sum()
        metricas['risco_ruptura_5d'] = (
            (df['cobertura_dias'] >= 3) & (df['cobertura_dias'] < 5)).sum()
        metricas['produtos_lentos'] = df[df['cobertura_dias']
                                         > 0]['sugestao'].sum()
    else:
        metricas['risco_ruptura_3d'] = 0
        metricas['risco_ruptura_5d'] = 0
        metricas['produtos_lentos'] = 0

    # Data da análise
    if 'data' in df.columns:
        metricas['data_analise'] = str(df['data'].iloc[0])
    else:
        metricas['data_analise'] = datetime.now().strftime('%Y-%m-%d')

    return metricas


# =========================================================
# CRIAÇÃO DE GRÁFICOS
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
    fig.update_layout(height=400, showlegend=True)
    return fig


def criar_grafico_situacoes(metricas):
    """Cria gráfico de pizza de situações"""
    fig = go.Figure(data=[
        go.Pie(
            labels=[
                f"Atendimento ({metricas['em_atendimento']:,})",
                f"Insuficiente ({metricas['insuficiente']:,})",
                f"Falta Estoque ({metricas['falta_estoque']:,})",
                f"Aguardando ({metricas['aguardando_giro']:,})"
            ],
            values=[
                metricas['em_atendimento'],
                metricas['insuficiente'],
                metricas['falta_estoque'],
                metricas['aguardando_giro']
            ],
            marker=dict(colors=['#2ecc71', '#f39c12', '#e74c3c', '#3498db']),
            textposition='inside',
            textinfo='label+percent',
            insidetextorientation='horizontal'
        )
    ])
    fig.update_layout(height=400, showlegend=True)
    return fig


def criar_comparacao_loja_vs_cd(metricas):
    """Cria gráfico de barras comparando giro lojas vs CD"""
    giro_medio_lojas = metricas['giro_medio_geral']
    giro_cd = metricas['giro_cd']

    fig = go.Figure()

    # Barra Lojas
    fig.add_trace(go.Bar(
        x=['Lojas'],
        y=[giro_medio_lojas],
        name='Lojas',
        marker_color='#3498db',
        text=[f"{giro_medio_lojas:.1f}d"],
        textposition='outside'
    ))

    # Barra CD
    fig.add_trace(go.Bar(
        x=['CD'],
        y=[giro_cd],
        name='CD',
        marker_color='#e74c3c',
        text=[f"{giro_cd:.1f}d"],
        textposition='outside'
    ))

    # Linha ideal
    fig.add_hline(y=90, line_dash="dash", line_color="green",
                  annotation_text="Ideal CD (90d)", annotation_position="top right")

    fig.update_layout(
        title="Giro Médio: Lojas vs CD",
        xaxis_title="Nível",
        yaxis_title="Dias de Cobertura",
        height=400,
        showlegend=False
    )

    return fig


def criar_gauge_giro_medio(giro_medio):
    """Cria gauge de giro médio"""
    # Determinar cor baseado no valor
    if giro_medio < 22:
        cor = "#27ae60"
    elif giro_medio <= 30:
        cor = "#f39c12"
    else:
        cor = "#e74c3c"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=giro_medio,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Giro Médio (dias)"},
        number={'suffix': " dias", 'font': {'size': 40}},
        gauge={
            'axis': {'range': [None, 50], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': cor},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 22], 'color': 'rgba(39, 174, 96, 0.3)'},
                {'range': [22, 30], 'color': 'rgba(243, 156, 18, 0.3)'},
                {'range': [30, 50], 'color': 'rgba(231, 76, 60, 0.3)'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 30
            }
        }
    ))

    fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
    return fig


def criar_grafico_risco_ruptura(metricas):
    """Cria gráfico de barras de risco de ruptura"""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=['<3 dias', '3-5 dias'],
        y=[metricas['risco_ruptura_3d'], metricas['risco_ruptura_5d']],
        marker_color=['#e74c3c', '#f39c12'],
        text=[metricas['risco_ruptura_3d'], metricas['risco_ruptura_5d']],
        textposition='outside'
    ))

    fig.update_layout(
        title="Risco de Ruptura",
        xaxis_title="",
        yaxis_title="Quantidade",
        height=350,
        showlegend=False
    )

    return fig


def criar_grafico_giro_lojas_top20(metricas):
    """Cria gráfico horizontal de giro por loja (Top 20)"""
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
        height=600,
        margin=dict(l=150, r=100, t=80, b=60)
    )

    return fig


def criar_tabela_detalhes_lojas(metricas):
    """Cria DataFrame com detalhes de todas as lojas"""
    if not metricas['giro_por_loja']:
        return None

    df_lojas = pd.DataFrame(
        list(metricas['giro_por_loja'].items()),
        columns=['Loja', 'Giro (dias)']
    ).sort_values('Giro (dias)', ascending=False)

    df_lojas['Loja'] = 'Loja ' + df_lojas['Loja'].astype(str)
    df_lojas['Giro (dias)'] = df_lojas['Giro (dias)'].round(2)
    df_lojas.index = range(1, len(df_lojas) + 1)

    return df_lojas


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

    # SEÇÃO: VISÃO GERAL
    st.header("📊 Visão Geral")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Analisados",
            f"{metricas['total_analisados']:,}",
            delta=f"Com sugestão: {metricas['com_sugestao']:,}",
            delta_color="normal"
        )

    with col2:
        st.metric(
            "Em Atendimento",
            f"{metricas['em_atendimento']:,}",
            delta=f"↑ {(metricas['em_atendimento']/metricas['total_analisados']*100) if metricas['total_analisados'] > 0 else 0:.1f}%",
            delta_color="normal",
            help="Produtos com sugestão IA (caixas sugeridas + pendentes)"
        )

    with col3:
        st.metric(
            "Insuficiente",
            f"{metricas['insuficiente']:,}",
            delta=f"↑ {(metricas['insuficiente']/metricas['total_analisados']*100) if metricas['total_analisados'] > 0 else 0:.1f}%",
            delta_color="normal"
        )

    with col4:
        st.metric(
            "Falta Estoque",
            f"{metricas['falta_cd_total']:,}",
            delta=f"↑ {(metricas['falta_cd_total']/metricas['total_analisados']*100) if metricas['total_analisados'] > 0 else 0:.1f}%",
            delta_color="normal",
            help="Total pedido mas em falta ou insuficiente no CD"
        )

    st.markdown("---")

    # SEÇÃO 1: SUGESTÕES ML
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
        st.metric("Total Gerado", f"{metricas['total_gerado']:,} cx",
                  help="Original: Quantidade original planejada")
    with col2:
        st.metric("Total Sugerido", f"{metricas['total_sugerido']:,} cx",
                  help="ML: Quantidade sugerida pela IA")
    with col3:
        cor = "🟢" if metricas['variacao_perc'] < 0 else "🔴"
        st.metric("Variação", f"{metricas['variacao_perc']:+.2f}%", f"{cor}")

    st.markdown("---")

    # SEÇÃO 3: ANÁLISE DE GIRO DO CD
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
        msg = "CD girando muito lentamente. Risco de obsolescência."

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown(f"""
        <div style="background-color: {cor_giro}; color: white; padding: 20px; border-radius: 10px;">
            <h3 style="margin:0;">Dias de Cobertura do CD</h3>
            <h2 style="margin:10px 0;">{giro_cd:.1f} dias</h2>
            <p style="margin:0; font-size:14px;">{status}: {msg}</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.metric("Cobertura CD", f"{giro_cd:.1f}d",
                  delta="Dias" if giro_cd > 0 else None,
                  delta_color="inverse")

    # Expander explicativo
    with st.expander("ℹ️ Como é calculado?"):
        st.write("""
        **Fórmula:** Giro = Estoque Total CD ÷ (Sugestão Mensal ÷ 30)
        
        - **Saudável:** < 90 dias (🟢)
        - **Atenção:** 90-120 dias (🟠)
        - **Crítico:** > 120 dias (🔴)
        """)

    st.markdown("---")

    # SEÇÃO 4: COMPARAÇÃO GIRO LOJA VS CD
    st.header("📊 Comparação: Giro Loja vs CD")

    col1, col2 = st.columns([2, 1])

    with col1:
        fig_comp = criar_comparacao_loja_vs_cd(metricas)
        st.plotly_chart(fig_comp, use_container_width=True)

    with col2:
        # Card de destaque
        diferenca = metricas['giro_cd'] - metricas['giro_medio_geral']
        perc_diff = (diferenca / metricas['giro_medio_geral']
                     * 100) if metricas['giro_medio_geral'] > 0 else 0

        if metricas['giro_cd'] < metricas['giro_medio_geral']:
            status_comp = "✅ CD mais estável"
            msg_comp = f"O CD tem {abs(diferenca):.1f} dias a mais de cobertura (+{abs(perc_diff):.1f}% vs lojas)"
        else:
            status_comp = "⚠️ CD mais estável"
            msg_comp = f"O CD tem {diferenca:.1f} dias a mais de cobertura (+{perc_diff:.1f}% vs lojas)"

        st.success(status_comp)
        st.write(msg_comp)

        st.metric("Giro Médio Lojas", f"{metricas['giro_medio_geral']:.1f}d")
        st.metric("Giro do CD", f"{metricas['giro_cd']:.1f}d")
        st.metric("Diferença", f"+{diferenca:.1f}d")

    st.markdown("---")

    # SEÇÃO 5: PREVISÃO DE RUPTURA
    st.header("⚠️ Previsão de Ruptura")

    col1, col2 = st.columns(2)

    with col1:
        fig_ruptura = criar_grafico_risco_ruptura(metricas)
        st.plotly_chart(fig_ruptura, use_container_width=True)

    with col2:
        fig_gauge = criar_gauge_giro_medio(metricas['giro_medio_geral'])
        st.plotly_chart(fig_gauge, use_container_width=True)

    # Métricas de ruptura
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Produtos com <3 dias", f"{metricas['risco_ruptura_3d']:,}",
                  delta="Crítico" if metricas['risco_ruptura_3d'] > 0 else None,
                  delta_color="inverse")
    with col2:
        st.metric("Produtos com 3-5 dias", f"{metricas['risco_ruptura_5d']:,}",
                  delta="Alerta" if metricas['risco_ruptura_5d'] > 0 else None,
                  delta_color="inverse")
    with col3:
        st.metric("Ruptura Crítica", f"{metricas['risco_ruptura_3d']:,}",
                  help="Produtos <3 dias")

    st.markdown("---")

    # SEÇÃO 6: GIRO POR LOJA (TOP 20)
    st.header("🏪 Giro Médio por Loja")

    if metricas['giro_por_loja']:
        fig_lojas = criar_grafico_giro_lojas_top20(metricas)
        if fig_lojas:
            st.plotly_chart(fig_lojas, use_container_width=True)
    else:
        st.info("ℹ️ Sem dados de giro por loja disponíveis")

    st.markdown("---")

    # SEÇÃO 7: DETALHES POR LOJA (TABELA COMPLETA)
    st.header("📋 Detalhes por Loja")

    df_detalhes = criar_tabela_detalhes_lojas(metricas)
    if df_detalhes is not None:
        col1, col2 = st.columns([3, 1])

        with col1:
            st.dataframe(
                df_detalhes,
                use_container_width=True,
                height=400
            )

        with col2:
            st.metric("Máximo", f"{df_detalhes['Giro (dias)'].max():.1f}d")
            st.metric("Mínimo", f"{df_detalhes['Giro (dias)'].min():.1f}d")
            st.metric("Média", f"{metricas['giro_medio_geral']:.1f}d")

            # Distribuição
            st.write("**Distribuição:**")
            baixo = (df_detalhes['Giro (dias)'] < 22).sum()
            ideal = ((df_detalhes['Giro (dias)'] >= 22) & (
                df_detalhes['Giro (dias)'] <= 30)).sum()
            alto = (df_detalhes['Giro (dias)'] > 30).sum()

            st.write(f"- 🔴 Baixo: {baixo}")
            st.write(f"- 🟢 Ideal: {ideal}")
            st.write(f"- 🟠 Alto: {alto}")

    st.markdown("---")

    # SEÇÃO 8: RESUMO DE INDICADORES
    st.header("📊 Resumo de Indicadores")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.subheader("Sugestões")
        st.write(f"• **Com sugestão:** {metricas['com_sugestao']:,}")
        st.write(f"• **Sem sugestão:** {metricas['sem_sugestao']:,}")
        st.write(f"• **%:** {metricas['perc_sugestao']:.1f}%")

    with col2:
        st.subheader("Comparativo")
        st.write(f"• **Original:** {metricas['total_gerado']:,} cx")
        st.write(f"• **ML:** {metricas['total_sugerido']:,} cx")
        st.write(f"• **Variação:** {metricas['variacao_perc']:.2f}%")

    with col3:
        st.subheader("Giro")
        st.write(f"• **Giro Médio:** {metricas['giro_medio_geral']:.1f} dias")
        st.write(f"• **Giro CD:** {metricas['giro_cd']:.1f} dias")
        st.write(f"• **Produtos Lentos:** {metricas['produtos_lentos']:,}")

    with col4:
        st.subheader("Ruptura & Giro")
        st.write(f"• **Crítico:** {metricas['risco_ruptura_3d']:,} produtos")
        st.write(f"• **Alerta:** {metricas['risco_ruptura_5d']:,} produtos")
        st.write(f"• **Giro:** {metricas['giro_medio_geral']:.1f} dias")

    st.markdown("---")

    # RODAPÉ
    st.markdown(f"""
    <div style="text-align: center; color: #95a5a6; font-size: 12px;">
        Dashboard gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}
        <br>
        Dados: sugestao_ia (banco de dados ou arquivo parquet)
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
