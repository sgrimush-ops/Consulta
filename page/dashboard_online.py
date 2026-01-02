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
        .status-excelente {
            background-color: #d5f4e6;
            border-left: 4px solid #27ae60;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .status-atencao {
            background-color: #fef5e7;
            border-left: 4px solid #f39c12;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .status-critico {
            background-color: #fadbd8;
            border-left: 4px solid #e74c3c;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
    </style>
    """, unsafe_allow_html=True)


# =========================================================
# CARREGAMENTO DE DADOS
# =========================================================
def carregar_dados_parquet(base_path):
    """Carrega dados do sugestao_ia.parquet do diretório de dados (sem cache para atualização automática)"""
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


def carregar_dados_banco(_engine):
    """Carrega dados da tabela sugestao_ia do banco de dados (sem cache para atualização automática)"""
    try:
        with _engine.connect() as conn:
            df = pd.read_sql_table('sugestao_ia', con=conn)

            # Mostrar informações sobre a data dos dados
            if 'data_analise' in df.columns:
                data_mais_recente = pd.to_datetime(df['data_analise']).max()
                st.success(
                    f"✓ Dados carregados do banco: {len(df)} linhas | Data mais recente: {data_mais_recente.strftime('%d/%m/%Y')}")
            else:
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
        metricas['com_sugestao'] = (
            df['sugestao'] > 0).sum() if 'sugestao' in df.columns else 0
        metricas['sem_sugestao'] = (df['sugestao'] == 0).sum(
        ) if 'sugestao' in df.columns else metricas['total_analisados'] - metricas['com_sugestao']
        metricas['perc_sugestao'] = (
            metricas['com_sugestao'] / metricas['total_analisados'] * 100) if metricas['total_analisados'] > 0 else 0

    # Situações - Contabilizar pelos valores reais da coluna
    if 'situacao' in df.columns:
        situacoes = df['situacao'].value_counts()

        # Em Atendimento = 'em atendimento' (produtos que precisam ser enviados)
        # Também aceita 'enviar_pedido' por compatibilidade
        metricas['em_atendimento'] = situacoes.get('em atendimento', 0) + situacoes.get('enviar_pedido', 0)

        # Insuficiente = 'insuficiente' (produtos com estoque insuficiente)
        metricas['insuficiente'] = situacoes.get('insuficiente', 0)

        # Falta CD = 'falta_cd' ou 'falta de estoque' (produtos em falta no CD)
        metricas['falta_estoque'] = situacoes.get('falta_cd', 0) + situacoes.get('falta de estoque', 0)

        # Falta CD Total = falta_cd + insuficiente (tudo que não pode ser atendido)
        metricas['falta_cd_total'] = metricas['falta_estoque'] + \
            metricas['insuficiente']

        # Aguardando Giro = 'aguardando_giro' (produtos aguardando movimento)
        metricas['aguardando_giro'] = situacoes.get('aguardando_giro', 0)
    else:
        metricas['em_atendimento'] = 0
        metricas['insuficiente'] = 0
        metricas['falta_estoque'] = 0
        metricas['falta_cd_total'] = 0
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

    # Giro CD baseado em demanda (usando venda_media_dia - como no local)
    if 'estoque_total_cd' in df.columns and 'venda_media_dia' in df.columns:
        estoque_total_cd = df['estoque_total_cd'].sum()
        demanda_media_total = df['venda_media_dia'].sum()

        if demanda_media_total > 0:
            metricas['giro_cd'] = round(
                estoque_total_cd / demanda_media_total, 1)
        else:
            metricas['giro_cd'] = 0
    else:
        metricas['giro_cd'] = 0

    # Giro médio geral (dias_cobertura_atual - como no local)
    if 'dias_cobertura_atual' in df.columns:
        df_com_estoque = df[df['dias_cobertura_atual'] > 0]
        metricas['giro_medio_geral'] = round(
            df_com_estoque['dias_cobertura_atual'].mean(), 1
        ) if len(df_com_estoque) > 0 else 0
    else:
        metricas['giro_medio_geral'] = 0

    # Giro por loja (dias_cobertura_atual - como no local)
    metricas['giro_por_loja'] = {}
    if 'loja' in df.columns and 'dias_cobertura_atual' in df.columns:
        df_com_estoque = df[df['dias_cobertura_atual'] > 0]
        if len(df_com_estoque) > 0:
            giro_por_loja = df_com_estoque.groupby(
                'loja')['dias_cobertura_atual'].mean()
            for loja, giro in giro_por_loja.items():
                metricas['giro_por_loja'][str(loja)] = round(giro, 1)

    # Risco de ruptura (dias_cobertura_atual - como no local)
    if 'dias_cobertura_atual' in df.columns:
        metricas['risco_ruptura_3d'] = (df['dias_cobertura_atual'] < 3).sum()
        metricas['risco_ruptura_5d'] = (
            (df['dias_cobertura_atual'] >= 3) &
            (df['dias_cobertura_atual'] < 5)
        ).sum()
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
    fig.update_layout(height=400, showlegend=False)
    return fig


def criar_grafico_comparativo(metricas):
    """Cria gráfico comparativo Gerado vs Sugerido"""
    fig = go.Figure(data=[
        go.Bar(
            x=['Original', 'ML Sugerido'],
            y=[metricas['total_gerado'], metricas['total_sugerido']],
            marker=dict(color=['#3498db', '#e74c3c']),
            text=[
                f"{metricas['total_gerado']:,}",
                f"{metricas['total_sugerido']:,}"
            ],
            textposition='outside'
        )
    ])
    fig.update_layout(
        title="Comparativo Gerado vs Sugerido",
        yaxis_title="Quantidade (caixas)",
        height=350,
        showlegend=False
    )
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
        marker=dict(color=df_lojas['Cor'], line=dict(width=2, color='white')),
        text=df_lojas['Giro Médio (dias)'].round(1),
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Giro: %{x:.1f} dias<extra></extra>'
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

    st.set_page_config(
        page_title="Dashboard Sugestões IA",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("📊 DASHBOARD - ANÁLISE DE SUGESTÕES IA")

    # Botão para forçar atualização
    col_titulo1, col_titulo2 = st.columns([3, 1])
    with col_titulo1:
        st.info(
            "🔄 Os dados são carregados automaticamente a cada atualização da página")
    with col_titulo2:
        if st.button("🔄 Recarregar Dados", type="primary"):
            st.cache_data.clear()
            st.rerun()

    # Tentar carregar do banco automaticamente
    df = None

    if engine:
        with st.spinner("Carregando dados do banco..."):
            df = carregar_dados_banco(engine)

    # Se não conseguiu do banco, tentar carregar do arquivo local
    if df is None:
        if base_data_path:
            with st.spinner("Carregando arquivo local..."):
                df = carregar_dados_parquet(base_data_path)

        if df is None:
            st.error(
                "❌ Nenhum dado disponível. Configure o banco de dados ou um arquivo local.")
            st.stop()

    # Calcular métricas
    metricas = calcular_metricas(df)

    # Data da análise
    data_analise = (
        pd.to_datetime(df['data_analise'].iloc[0]).strftime('%d/%m/%Y')
        if 'data_analise' in df.columns else datetime.now().strftime('%d/%m/%Y')
    )
    st.markdown(f"**Data da análise:** {data_analise}")
    st.markdown("---")

    # ==============================================================================
    # SEÇÃO 1: VISÃO GERAL
    # ==============================================================================
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
            help="Produtos que precisam ser enviados (situacao: 'em atendimento' ou 'enviar_pedido')"
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
            help="Total em falta ou insuficiente no CD"
        )

    st.markdown("---")

    # ==============================================================================
    # SEÇÃO 2: SUGESTÕES E SITUAÇÕES (lado a lado)
    # ==============================================================================
    st.header("📊 Análise Detalhada")
    col1, col2 = st.columns(2)

    with col1:
        fig1 = criar_grafico_sugestoes(metricas)
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        fig2 = criar_grafico_situacoes(metricas)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # ==============================================================================
    # SEÇÃO 3: COMPARATIVO GERADO vs SUGERIDO
    # ==============================================================================
    st.header("📈 Comparativo: Gerado vs Sugerido")
    col1, col2, col3 = st.columns(3)

    with col1:
        fig3 = criar_grafico_comparativo(metricas)
        st.plotly_chart(fig3, use_container_width=True)

    with col2:
        st.metric("Total Gerado", f"{metricas['total_gerado']:,} cx")

    with col3:
        st.metric("Total Sugerido", f"{metricas['total_sugerido']:,} cx")

        variacao = metricas['variacao_perc']
        cor_var = "🔴" if variacao > 0 else "🟢" if variacao < 0 else "⚪"
        st.metric("Variação", f"{variacao:+.1f}%", f"{cor_var}")

    st.markdown("---")

    # ==============================================================================
    # SEÇÃO 4: ANÁLISE DE GIRO DO CD
    # ==============================================================================
    st.header("📦 Análise de Giro do CD")

    giro_cd = metricas['giro_cd']
    if giro_cd < 90:
        cor_giro = "#27ae60"
        status = "ÓTIMO"
        interpretacao = "CD com giro saudável. Estoque bem dimensionado."
    elif giro_cd <= 120:
        cor_giro = "#f39c12"
        status = "ATENÇÃO"
        interpretacao = "Giro acima do ideal. CD pode estar superabastecido."
    else:
        cor_giro = "#e74c3c"
        status = "CRÍTICO"
        interpretacao = "CD girando muito lentamente. Risco de obsolescência."

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown(f"""
        <div style="background-color: {cor_giro}; color: white; padding: 20px; 
                    border-radius: 10px;">
            <h3 style="margin:0;">Dias de Cobertura do CD</h3>
            <h2 style="margin:10px 0;">{giro_cd:.1f} dias</h2>
            <p style="margin:0; font-size:14px;">{status}: {interpretacao}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <details>
        <summary style="cursor:pointer; color:#666;">ℹ️ Como é calculado?</summary>
        <div style="padding:10px; background:#f5f5f5; border-radius:5px; 
                    margin-top:5px; font-size:12px;">
        <b>Giro CD = Estoque Total do CD / Demanda Média Diária</b><br><br>
        Mostra quantos dias o estoque total do CD consegue atender 
        a demanda combinada de todas as lojas.
        </div>
        </details>
        """, unsafe_allow_html=True)

    with col2:
        st.metric("Cobertura CD", f"{giro_cd:.1f}d", "Dias")

    st.markdown("---")

    # ==============================================================================
    # SEÇÃO 5: COMPARAÇÃO GIRO: LOJAS vs CD
    # ==============================================================================
    st.markdown("---")
    st.subheader("📊 Comparação: Giro Loja vs CD")

    if metricas['giro_por_loja']:
        giro_lojas = list(metricas['giro_por_loja'].values())
        giro_medio_loja = sum(giro_lojas) / \
            len(giro_lojas) if giro_lojas else 0

        col1, col2, col3 = st.columns(3)

        with col1:
            fig_comparacao = go.Figure(data=[
                go.Bar(
                    x=['Lojas', 'CD'],
                    y=[giro_medio_loja, giro_cd],
                    marker=dict(
                        color=['#3498db', '#e74c3c'],
                        line=dict(width=2, color='white')
                    ),
                    text=[f'{giro_medio_loja:.1f}d', f'{giro_cd:.1f}d'],
                    textposition='outside',
                    hovertemplate='<b>%{x}</b><br>Giro: %{y:.1f} dias<extra></extra>',
                    showlegend=False
                )
            ])

            fig_comparacao.add_hline(
                y=90, line_dash="dash", line_color="green",
                annotation_text="Ideal CD (90d)", annotation_position="right"
            )

            fig_comparacao.update_layout(
                title="Giro Médio: Lojas vs CD",
                xaxis_title="Nível",
                yaxis_title="Dias de Cobertura",
                height=350,
                margin=dict(l=50, r=50, t=60, b=50)
            )

            st.plotly_chart(fig_comparacao, use_container_width=True)

        with col2:
            diferenca = giro_cd - giro_medio_loja
            percentual = (diferenca / giro_medio_loja *
                          100) if giro_medio_loja > 0 else 0

            if diferenca > 0:
                st.success(f"""
                ✅ **CD mais estável**
                
                O CD tem {abs(diferenca):.1f} dias a mais de cobertura
                ({percentual:+.1f}% vs lojas)
                """)
            elif diferenca < -1:
                st.error(f"""
                ⚠️ **CD subdimensionado**
                
                O CD tem {abs(diferenca):.1f} dias a menos
                ({percentual:+.1f}% vs lojas)
                """)
            else:
                st.info(f"""
                ℹ️ **Níveis similares**
                
                CD e lojas com giro próximo
                ({percentual:+.1f}%)
                """)

        with col3:
            st.metric("Giro Médio Lojas", f"{giro_medio_loja:.1f}d")
            st.metric("Giro do CD", f"{giro_cd:.1f}d")
            st.metric("Diferença", f"{diferenca:+.1f}d")

    st.markdown("---")

    # ==============================================================================
    # SEÇÃO 6: RISCO DE RUPTURA
    # ==============================================================================
    st.header("⚠️ Previsão de Ruptura")

    col1, col2, col3 = st.columns(3)

    with col1:
        fig5 = go.Figure(data=[
            go.Bar(
                x=['< 3 dias', '3-5 dias'],
                y=[
                    metricas['risco_ruptura_3d'],
                    metricas['risco_ruptura_5d']
                ],
                marker=dict(color=['#e74c3c', '#f39c12']),
                text=[
                    metricas['risco_ruptura_3d'],
                    metricas['risco_ruptura_5d']
                ],
                textposition='outside'
            )
        ])
        fig5.update_layout(
            title="Risco de Ruptura",
            yaxis_title="Quantidade",
            height=300,
            showlegend=False
        )
        st.plotly_chart(fig5, use_container_width=True)

    with col2:
        giro = metricas['giro_medio_geral']
        cor_giro = "#e74c3c" if giro < 4 else "#27ae60" if giro <= 6 else "#f39c12"
        status_giro = "BAIXO" if giro < 4 else "IDEAL" if giro <= 6 else "ALTO"

        fig6 = go.Figure(data=[
            go.Indicator(
                mode="gauge+number",
                value=giro,
                title="Giro Médio (dias)",
                gauge={
                    'axis': {'range': [0, 50]},
                    'bar': {'color': cor_giro},
                    'steps': [
                        {'range': [0, 4], 'color': "#fadbd8"},
                        {'range': [4, 6], 'color': "#d5f4e6"},
                        {'range': [6, 50], 'color': "#fef5e7"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 6
                    }
                }
            )
        ])
        fig6.update_layout(height=300)
        st.plotly_chart(fig6, use_container_width=True)

    with col3:
        st.metric(
            "Giro Médio (Loja)",
            f"{giro:.1f} dias"
        )

        st.metric(
            "Giro do CD",
            f"{metricas['giro_cd']:.1f} dias"
        )

        st.metric(
            "Ruptura Crítica",
            f"{metricas['risco_ruptura_3d']}"
        )

    st.markdown("---")

    # ==============================================================================
    # SEÇÃO 7: GIRO POR LOJA (Tabela Detalhada)
    # ==============================================================================
    st.header("🏪 Giro Médio por Loja")

    if metricas['giro_por_loja']:
        df_lojas = pd.DataFrame(
            list(metricas['giro_por_loja'].items()),
            columns=['Loja', 'Giro Médio (dias)']
        ).sort_values('Giro Médio (dias)', ascending=False)

        df_lojas['Loja_Label'] = 'Loja ' + df_lojas['Loja'].astype(str)

        def get_color_giro(valor):
            if valor < 22:
                return '#27ae60'
            elif valor <= 30:
                return '#f39c12'
            else:
                return '#e74c3c'

        df_lojas['Cor'] = df_lojas['Giro Médio (dias)'].apply(get_color_giro)

        fig7 = go.Figure()

        fig7.add_trace(go.Bar(
            y=df_lojas['Loja_Label'].head(20),
            x=df_lojas['Giro Médio (dias)'].head(20),
            orientation='h',
            marker=dict(
                color=df_lojas['Cor'].head(20),
                line=dict(width=2, color='white')
            ),
            text=df_lojas['Giro Médio (dias)'].head(20).round(1),
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Giro: %{x:.1f} dias<extra></extra>',
            showlegend=False
        ))

        fig7.add_vline(x=22, line_dash="dash", line_color="green",
                       line_width=2, annotation_text="Saudável (22d)",
                       annotation_position="top right")
        fig7.add_vline(x=30, line_dash="dash", line_color="red",
                       line_width=2, annotation_text="Alto (30d)",
                       annotation_position="top right")

        fig7.update_layout(
            title={
                'text': "Giro Médio por Loja (Top 20)",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18, 'color': '#2c3e50'}
            },
            xaxis_title="Dias de Cobertura",
            yaxis_title="Loja",
            yaxis=dict(
                tickfont=dict(size=12, color='#2c3e50', family='Arial Black')
            ),
            xaxis=dict(
                tickfont=dict(size=11)
            ),
            height=500,
            showlegend=False,
            hovermode='closest',
            margin=dict(l=150, r=100, t=80, b=60)
        )

        fig7.add_annotation(
            text="<b>Legenda:</b> <span style='color:#27ae60'>●</span> Saudável (<22d) " +
                 "<span style='color:#f39c12'>●</span> Atenção (22-30d) " +
                 "<span style='color:#e74c3c'>●</span> Alto (>30d)",
            xref="paper", yref="paper",
            x=0.5, y=-0.12,
            showarrow=False,
            xanchor='center',
            font=dict(size=11)
        )

        st.plotly_chart(fig7, use_container_width=True)

        st.subheader("📊 Detalhes por Loja")

        df_tabela = df_lojas[['Loja_Label', 'Giro Médio (dias)']].copy()
        df_tabela['Giro Médio (dias)'] = df_tabela['Giro Médio (dias)'].round(
            2)
        df_tabela.columns = ['Loja', 'Giro (dias)']
        df_tabela = df_tabela.reset_index(drop=True)
        df_tabela.index = df_tabela.index + 1

        col1, col2 = st.columns([3, 1])
        with col1:
            st.dataframe(
                df_tabela,
                use_container_width=True,
                height=400,
                column_config={
                    "Loja": st.column_config.TextColumn("🏪 Loja", width="large"),
                    "Giro (dias)": st.column_config.NumberColumn(
                        "📈 Giro (dias)",
                        format="%.2f"
                    )
                }
            )

        with col2:
            st.metric("Máximo", f"{df_lojas['Giro Médio (dias)'].max():.1f}d")
            st.metric("Mínimo", f"{df_lojas['Giro Médio (dias)'].min():.1f}d")
            st.metric("Média", f"{df_lojas['Giro Médio (dias)'].mean():.1f}d")

            qtd_baixo = (df_lojas['Giro Médio (dias)'] < 22).sum()
            qtd_ideal = ((df_lojas['Giro Médio (dias)'] >= 22) &
                         (df_lojas['Giro Médio (dias)'] <= 30)).sum()
            qtd_alto = (df_lojas['Giro Médio (dias)'] > 30).sum()

            st.markdown(f"""
            **Distribuição:**
            - 🟢 Saudável: {qtd_baixo}
            - 🟠 Atenção: {qtd_ideal}
            - 🔴 Alto: {qtd_alto}
            """)
    else:
        st.info("Dados de loja não disponíveis")

    st.markdown("---")

    # ==============================================================================
    # SEÇÃO 8: RESUMO DE INDICADORES
    # ==============================================================================
    st.header("📋 Resumo de Indicadores")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        ### Sugestões 🎯
        - **Com sugestão:** {metricas['com_sugestao']:,}
        - **Sem sugestão:** {metricas['sem_sugestao']:,}
        - **%:** {metricas['com_sugestao']/metricas['total_analisados']*100:.1f}%
        """)

    with col2:
        st.markdown(f"""
        ### Comparativo 📊
        - **Original:** {metricas['total_gerado']:,} cx
        - **ML:** {metricas['total_sugerido']:,} cx
        - **Variação:** {metricas['variacao_perc']:+.1f}%
        """)

    with col3:
        st.markdown(f"""
        ### Giro 📈
        - **Giro Médio:** {metricas['giro_medio_geral']:.1f} dias
        - **Giro CD:** {metricas['giro_cd']:.1f} dias
        - **Produtos Lentos:** {metricas['risco_ruptura_5d']}
        """)

    with col4:
        st.markdown(f"""
        ### Ruptura & Giro ⚠️
        - **Crítico:** {metricas['risco_ruptura_3d']} produtos
        - **Alerta:** {metricas['risco_ruptura_5d']} produtos
        - **Giro:** {metricas['giro_medio_geral']:.1f} dias
        """)

    st.markdown("---")

    # ==============================================================================
    # RODAPÉ
    # ==============================================================================
    st.markdown(f"""
    <div style="text-align: center; color: #95a5a6; font-size: 12px;">
        Dashboard gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}
        <br>
        Data de análise: {data_analise}
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
