# Skill: Manipulação Robusta de Arquivos Parquet

## Contexto do ProjetoBak

O aplicativo ProjetoBak usa **Parquet como formato canônico** para armazenamento de dados estruturados:

```
bdados/
├── con5cod.parquet          # Catálogo de produtos (Consinco)
├── consumo.parquet          # Histórico de consumo por loja
├── ean_dun.parquet          # Mapeamento EAN/DUN por produto (Admin Uploads)
└── query.parquet            # Embalagem de transferência por produto (Admin Uploads)
```

> **Atenção**: `ean_dun.parquet` e `query.parquet` **não ficam no Git**.
> Devem ser carregados via `page/admin_uploads.py` para o disco persistente no Render.

**Parquet** é um formato **columnar, comprimido e tipado** que oferece:
- ✅ Compressão automática (reduz tamanho em 70-90% vs CSV)
- ✅ Leitura parcial (carrega só colunas necessárias)
- ✅ Tipos de dados preservados (int, float, string, date)
- ✅ Suporte a arquivos grandes (>1 GB)
- ✅ Otimizado para analytics + data science

## Como Parquet é Usado no ProjetoBak

### 1. **Carregamento de Produtos** (`utils/produtos_loader.py`)

```python
# Parquet é a fonte de verdade para catálogo
df_parquet = pd.read_parquet("bdados/con5cod.parquet")

# Normaliza colunas vinindo do ERP Consinco
column_mapping = {
    'codigoconsinco': 'cod_consinco',
    'Empresa : Produto': 'descricao',
    'embalagem': 'Emb',
    'ltmix': 'Mix',
}
df_parquet.rename(columns=column_mapping, inplace=True)

# Mescla com customizações do banco (custom sempre prevalece)
df_final = pd.concat([
    df_custom[cols_finais],
    df_parquet[cols_finais]
], ignore_index=True)
```

### 2. **Dados de Consumo** (`bdados/consumo.parquet`)

```python
# Carrega CSV com problemas
df = pd.read_csv("consumo_sujo.csv")

# Limpa e valida
df = _sanitizar_consumo(df)

# Exporta para parquet para próximas execuções
df.to_parquet("bdados/consumo.parquet", engine='pyarrow')
```

### 3. **EAN/DUN por Produto** (`bdados/ean_dun.parquet`)

```python
df_ean = pd.read_parquet("bdados/ean_dun.parquet")

# Normaliza colunas (schema pode variar por exportação do ERP)
df_ean.columns = [c.lower().strip().replace(' ', '_') for c in df_ean.columns]

# Colunas esperadas após normalização: codigo_produto, ean_dun
df_ean['ean_dun'] = df_ean['ean_dun'].astype(str).str.strip()

# Equivalência EAN-13 ↔ GTIN-14 (comum em base DUN)
def buscar_por_ean(df_ean, codigo):
    variantes = {str(codigo).strip().zfill(13), str(codigo).strip().zfill(14)}
    return df_ean[df_ean['ean_dun'].isin(variantes)]
```

### 4. **Embalagem de Transferência** (`bdados/query.parquet`)

```python
df_query = pd.read_parquet("bdados/query.parquet")
df_query.columns = [c.lower().strip().replace(' ', '_') for c in df_query.columns]

# Mesclar embalagem ao resultado de produto por cod_consinco
resultado = resultado.merge(
    df_query[['cod_consinco', 'embalagem_de_transferencia']],
    on='cod_consinco', how='left'
)
```

## Operações Comuns com Parquet

### **1. Ler Parquet (com filtros opcionais)**

```python
import pandas as pd
import pyarrow.parquet as pq

# Ler arquivo inteiro
df = pd.read_parquet("bdados/con5cod.parquet")

# Ler colunas específicas (mais rápido)
df = pd.read_parquet(
    "bdados/con5cod.parquet",
    columns=['cod_consinco', 'descricao', 'Mix']
)

# Ler com filtro (push-down, muito eficaz)
table = pq.read_table(
    "bdados/con5cod.parquet",
    filters=[('Mix', '==', 'A')]  # Só produtos ativos
)
df = table.to_pandas()
```

### **2. Escrever Parquet**

```python
df.to_parquet(
    "bdados/consumo.parquet",
    engine='pyarrow',
    compression='snappy',
    index=False
)
```

### **3. Inspecionar Parquet**

```python
import pyarrow.parquet as pq

parquet_file = pq.ParquetFile("bdados/con5cod.parquet")
print(f"Linhas: {parquet_file.num_rows}")
print(f"Schema: {parquet_file.schema}")
```

### **4. Validações de Integridade**

```python
def validar_parquet(caminho_arquivo):
    try:
        df = pd.read_parquet(caminho_arquivo)
        assert df.shape[0] > 0, "Arquivo está vazio"
        assert df.shape[1] > 0, "Nenhuma coluna encontrada"
        n_dup = df.duplicated().sum()
        if n_dup > 0:
            print(f"⚠️  {n_dup} linhas duplicadas")
        return True, f"✅ Parquet válido: {df.shape[0]} linhas, {df.shape[1]} colunas"
    except Exception as e:
        return False, f"❌ Erro ao ler parquet: {e}"
```

### **5. Converter CSV → Parquet**

```python
df = pd.read_csv("dados.csv", sep=';', encoding='utf-8')
assert not df[['cod_consinco']].duplicated().any(), "Códigos duplicados!"
df.to_parquet("bdados/dados.parquet", engine='pyarrow', compression='snappy', index=False)
```

### **6. Mesclar Múltiplos Parquets**

```python
import glob
arquivos = glob.glob("bdados/consumo_*/*.parquet")
dfs = [pd.read_parquet(a) for a in arquivos]
df_total = pd.concat(dfs, ignore_index=True)
df_total.to_parquet("bdados/consumo_consolidado.parquet")
```

## Parquet no Deploy do Render

### Arquivos que NÃO ficam no Git
- `ean_dun.parquet` e `query.parquet` são carregados via **Admin Uploads**.
- `con5cod.parquet` e `consumo.parquet` podem ser commitados ou enviados via upload.
- O cwd do container Render pode diferir do ambiente local.

### Resolução de Caminho (Padrão Anti-Deploy-Fail)

```python
import os, pathlib

def resolver_parquet(nome_arquivo, env_var=None):
    """Resolve caminho de Parquet compativel com Render e ambiente local."""
    if env_var and os.getenv(env_var):
        return os.getenv(env_var)
    base_disk = os.getenv('RENDER_DISK_PATH', '')
    candidatos = [
        pathlib.Path(__file__).parent.parent / 'bdados' / nome_arquivo,
        pathlib.Path(base_disk) / 'bdados' / nome_arquivo if base_disk else None,
        pathlib.Path('/opt/render/project/src/bdados') / nome_arquivo,
        pathlib.Path('bdados') / nome_arquivo,
    ]
    for c in candidatos:
        if c and c.exists():
            return str(c)
    return None  # Arquivo nao encontrado em nenhum candidato

# Uso:
path_ean = resolver_parquet('ean_dun.parquet', 'EAN_DUN_PARQUET_PATH')
path_query = resolver_parquet('query.parquet', 'QUERY_PARQUET_PATH')
```

### apt.txt para Libs de Sistema

```
libzbar0   # pyzbar (leitura de codigo de barras)
ffmpeg     # av/streamlit-webrtc
```

### Imports Opcionais (evitar crash por dependência ausente)

```python
try:
    import av
    import cv2
    from pyzbar import pyzbar
    from streamlit_webrtc import webrtc_streamer, VideoProcessorBase
    CAMERA_DISPONIVEL = True
except ImportError:
    CAMERA_DISPONIVEL = False
```

## Padrões de Boas Práticas

### **✅ Fazer**
- Ler só colunas necessárias (reduz memória)
- Usar filtros no nível do Parquet (push-down)
- Normalizar colunas antes de mapear (lower, strip, replace espaços)
- Adicionar coluna de origem ao mesclar
- Resolver caminhos por múltiplos candidatos no Render

### **❌ Não Fazer**
- Ler arquivo inteiro se só precisa de subset
- Converter Parquet → CSV → Parquet (perda de tipos)
- Assumir que coluna existe sem validar
- Commitar Parquets grandes no Git (usar Admin Uploads)
- Import direto no topo de libs opcionais (derruba o app)

## Checklist para Trabalhar com Parquet

- [ ] Arquivo parquet existe no caminho correto?
- [ ] Consigo ler com `pd.read_parquet()`?
- [ ] Colunas normalizadas e mapeadas?
- [ ] Sem linhas duplicadas críticas?
- [ ] Arquivo disponível no Render (via Admin Uploads)?
- [ ] Caminhos resolvidos por múltiplos candidatos?

## Dependências Já Instaladas

```
pyarrow==23.0.1              # ← Já em requirements.txt
pandas==2.2.3                # ← Já em requirements.txt
```

## Exemplos de Tarefas Típicas

### **Tarefa 1: Carregar apenas ativos para análise**

```python
df = pd.read_parquet("bdados/con5cod.parquet", columns=['cod_consinco', 'descricao', 'Emb'])
df = df[df['Mix'] == 'A']
```

### **Tarefa 2: Validar integridade antes de usar**

```python
from pyarrow.parquet import ParquetFile
pf = ParquetFile("bdados/con5cod.parquet")
print(f"Linhas: {pf.num_rows}, Schema: {pf.schema}")
```

### **Tarefa 3: Mesclar custom + parquet (padrão ProjetoBak)**

```python
df_custom = pd.read_sql("SELECT * FROM produtos_custom", engine)
df_parquet = pd.read_parquet("bdados/con5cod.parquet")
codigos_custom = set(df_custom['cod_consinco'].values)
df_parquet = df_parquet[~df_parquet['cod_consinco'].isin(codigos_custom)]
df_final = pd.concat([df_custom, df_parquet], ignore_index=True)
```

### **Tarefa 4: Buscar produto por EAN**

```python
df_ean = pd.read_parquet("bdados/ean_dun.parquet")
df_ean.columns = [c.lower().strip().replace(' ', '_') for c in df_ean.columns]
variantes = {ean.zfill(13), ean.zfill(14)}
resultado = df_ean[df_ean['ean_dun'].isin(variantes)]
```

## Integração com Agentes

**Danilo Dados**: carrega consumo/produtos, calcula ROP/cobertura.

**Ale Governança**: audita schema, detecta inconsistências, valida ean_dun e query.

**Anton Software**: resolve caminhos no Render, gerencia Admin Uploads, valida apt.txt.

**Roberta Relatórios**: agrega consumo, exporta para dashboard.

## Referências

- Docs PyArrow: https://arrow.apache.org/docs/python/
- Pandas Parquet: https://pandas.pydata.org/docs/user_guide/io.html#parquet
- `utils/produtos_loader.py`: Exemplo de leitura + mesclagem
- `page/admin_uploads.py`: Upload de Parquet para disco persistente no Render
- `requirements.txt`: `pyarrow==23.0.1`
- `apt.txt`: libs de sistema para pyzbar/av
