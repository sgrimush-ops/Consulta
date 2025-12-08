# 📊 Relatório de Cálculos do Dashboard de Estoque

## 1. **Entrada de Dados**

- **Arquivo de entrada:** `sugestao_ia.parquet`
- **Origem:** Gerado localmente pelo script de cálculo principal
- **No ambiente online:** O arquivo será lido do caminho configurado no Render/servidor (exemplo: `/mnt/data/sugestao_ia.parquet`)

---

## 2. **Leitura dos Dados**

```python
import pandas as pd
df = pd.read_parquet('sugestao_ia.parquet')
```

---

## 3. **Cálculo das Métricas Principais**

### 3.1. **Total de Produtos Analisados**
```python
total_analisados = len(df)
```

### 3.2. **Sugestões de Reposição**
- Se existirem as colunas `sugestao_caixa` e `sugestao_pendente`:
    ```python
    df['sugestao_total'] = df['sugestao_caixa'].fillna(0) + df['sugestao_pendente'].fillna(0)
    com_sugestao = (df['sugestao_total'] > 0).sum()
    sem_sugestao = (df['sugestao_total'] == 0).sum()
    ```
- Caso contrário:
    ```python
    com_sugestao = (df['sugestao'] > 0).sum()
    sem_sugestao = (df['sugestao'] == 0).sum()
    ```

### 3.3. **Situação dos Pedidos**
```python
situacoes = df['situacao'].value_counts()
falta_estoque = situacoes.get('falta de estoque', 0)
insuficiente = situacoes.get('insuficiente', 0)
em_atendimento = situacoes.get('em atendimento', 0)
aguardando_giro = situacoes.get('aguardando_giro', 0)
```

### 3.4. **Comparativo Gerado vs Sugerido**
```python
if 'gerado' in df.columns and 'sugestao' in df.columns:
    df_comp = df[df['sugestao'] > 0].copy()
    total_gerado = df_comp['gerado'].sum()
    total_sugerido = df_comp['sugestao'].sum()
    variacao_perc = ((total_sugerido - total_gerado) / total_gerado * 100) if total_gerado > 0 else 0
else:
    total_gerado = 0
    total_sugerido = df['sugestao'].sum() if 'sugestao' in df.columns else 0
    variacao_perc = 0
```

---

## 4. **Cálculo de Giro**

### 4.1. **Giro do CD**
```python
if 'estoque_total_cd' in df.columns and 'sugestao' in df.columns:
    df_com_sugestao = df[df['sugestao'] > 0]
    if len(df_com_sugestao) > 0:
        sugestao_diaria = df_com_sugestao['sugestao'].sum() / 30
        estoque_total_cd = df_com_sugestao['estoque_total_cd'].sum()
        giro_cd = estoque_total_cd / sugestao_diaria if sugestao_diaria > 0 else 0
    else:
        giro_cd = 0
else:
    giro_cd = 0
```

### 4.2. **Giro por Loja**
```python
giro_por_loja = {}
if 'loja' in df.columns and 'estoque_total_loja' in df.columns:
    for loja in df['loja'].unique():
        df_loja = df[(df['loja'] == loja) & (df['sugestao'] > 0)]
        if len(df_loja) > 0:
            sugestao_diaria_loja = df_loja['sugestao'].sum() / 30
            estoque_loja = df_loja['estoque_total_loja'].sum()
            giro = estoque_loja / sugestao_diaria_loja if sugestao_diaria_loja > 0 else 0
            giro_por_loja[str(loja)] = giro
giro_medio_geral = sum(giro_por_loja.values()) / len(giro_por_loja) if giro_por_loja else 0
```

---

## 5. **Risco de Ruptura**

```python
if 'cobertura_dias' in df.columns:
    risco_ruptura_3d = (df['cobertura_dias'] < 3).sum()
    risco_ruptura_5d = (df['cobertura_dias'] < 5).sum()
else:
    risco_ruptura_3d = 0
    risco_ruptura_5d = 0
```

---

## 6. **Data de Análise**

```python
if 'data' in df.columns:
    data_analise = str(df['data'].iloc[0])
else:
    from datetime import datetime
    data_analise = datetime.now().strftime('%Y-%m-%d')
```

---

## 7. **Como Replicar no Ambiente Online**

- **Passo 1:** Faça upload do arquivo `sugestao_ia.parquet` para o diretório de dados do seu servidor (exemplo: `/mnt/data/` no Render).
- **Passo 2:** No seu dashboard online, use o mesmo código acima para calcular todas as métricas e gerar os gráficos.
- **Passo 3:** Os gráficos e indicadores serão idênticos ao ambiente local, pois toda a lógica é baseada apenas no Parquet.

---

## 8. **Observações**

- O ambiente online não precisa de nenhum arquivo extra além do Parquet e do script do dashboard.
- Todos os cálculos são feitos em tempo real, garantindo que o resultado seja sempre igual ao local.
- Se quiser, pode salvar este relatório como `RELATORIO_CALCULOS.md` para consulta e documentação.

---

**Caminho do Parquet no ambiente online:**  
`/mnt/data/sugestao_ia.parquet`  
*(ajuste conforme o local de upload do seu serviço Render ou outro servidor)*
