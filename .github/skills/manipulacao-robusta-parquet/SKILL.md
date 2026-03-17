# Skill: Manipulação Robusta de Arquivos Parquet

## Contexto do ProjetoBak

O aplicativo ProjetoBak usa **Parquet como formato canônico** para armazenamento de dados estruturados:

```
bdados/
├── con5cod.parquet          # Catálogo de produtos (Consinco)
├── consumo.parquet          # Histórico de consumo por loja
```

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

CSV de entrada é exportado para Parquet após sanitização:

```python
# Carrega CSV com problemas
df = pd.read_csv("consumo_sujo.csv")

# Limpa e valida
df = _sanitizar_consumo(df)

# Exporta para parquet para próximas execuções
df.to_parquet("bdados/consumo.parquet", engine='pyarrow')
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
# Exportar DataFrame para Parquet
df.to_parquet(
    "bdados/consumo.parquet",
    engine='pyarrow',
    compression='snappy',  # ou 'gzip', 'brotli'
    index=False
)

# Com particionamento (para arquivos muito grandes)
df.to_parquet(
    "bdados/consumo_particionado/",
    partition_cols=['loja_id'],  # Cria subpastas por loja
    engine='pyarrow'
)
```

### **3. Inspecionar Parquet**

```python
import pyarrow.parquet as pq

# Ler metadados sem carregar dados
parquet_file = pq.ParquetFile("bdados/con5cod.parquet")

# Número de linhas
num_rows = parquet_file.num_rows
# 50000

# Schema (tipos de dados)
schema = parquet_file.schema
# cod_consinco: int64
# descricao: string
# Emb: int32
# Mix: string

# Tamanho físico (comprimido)
metadata = parquet_file.metadata
compressed_size = metadata.size
# "2.5 MB"

# Informações de particionamento
print(parquet_file.schema_arrow)
```

### **4. Validações de Integridade**

```python
import pandas as pd

def validar_parquet(caminho_arquivo):
    """Valida integridade de arquivo parquet."""
    
    try:
        # Tentativa de leitura
        df = pd.read_parquet(caminho_arquivo)
        
        # Validações
        assert df.shape[0] > 0, "Arquivo está vazio"
        assert df.shape[1] > 0, "Nenhuma coluna encontrada"
        
        # Linhas duplicadas
        n_duplicados = df.duplicated().sum()
        if n_duplicados > 0:
            print(f"⚠️  AVISO: {n_duplicados} linhas duplicadas")
        
        # Valores nulos críticos
        for col in df.columns:
            n_nulos = df[col].isna().sum()
            if n_nulos > 0:
                print(f"⚠️  AVISO: {col} tem {n_nulos} valores nulos")
        
        return True, f"✅ Parquet válido: {df.shape[0]} linhas, {df.shape[1]} colunas"
    
    except Exception as e:
        return False, f"❌ Erro ao ler parquet: {e}"
```

### **5. Converter CSV → Parquet**

```python
import pandas as pd

# Carregar CSV com encoding correto
df = pd.read_csv(
    "dados.csv",
    sep=';',
    encoding='utf-8',
    dtype={'cod_consinco': 'int64', 'Mix': 'string'}
)

# Validar antes de exportar
assert not df[['cod_consinco']].duplicated().any(), "Códigos duplicados!"

# Exportar para Parquet
df.to_parquet(
    "bdados/dados.parquet",
    engine='pyarrow',
    compression='snappy',
    index=False
)

print(f"✅ Convertido: {df.shape[0]} linhas para Parquet")
```

### **6. Mesclar Múltiplos Parquets**

```python
import pandas as pd
import glob

# Ler todos os parquets de um diretório
arquivos = glob.glob("bdados/consumo_*/consumo_*.parquet")

dfs = [
    pd.read_parquet(arquivo)
    for arquivo in arquivos
]

# Concatenar
df_total = pd.concat(dfs, ignore_index=True)

# Exportar resultado
df_total.to_parquet("bdados/consumo_consolidado.parquet")
```

## Padrões de Boas Práticas

### **✅ Fazer**
- Ler só colunas necessárias (reduz memória)
- Usar filtros no nível do Parquet (push-down)
- Definir tipos de dados explicitamente
- Adicionar coluna de origem (`origem = 'Parquet'`) ao mesclar
- Documentar schema e mapeamento de colunas

### **❌ Não Fazer**
- Ler arquivo inteiro se só precisa de subset
- Converter Parquet → CSV → Parquet (perda de tipos)
- Sobrescrever Parquet sem backup
- Assumir que coluna existe sem validar primeiro
- Ignorar avisos de duplicatas/nulos

## Checklist para Trabalhar com Parquet

- [ ] Arquivo parquet existe em `bdados/`?
- [ ] Consigo ler com `pd.read_parquet()`?
- [ ] Schema está correto (tipos de dados)?
- [ ] Sem linhas duplicadas críticas?
- [ ] Sem valores nulos onde não esperado?
- [ ] Tamanho do arquivo é razoável (<1 GB descomprimido)?
- [ ] Se modifico, valido antes de sobrescrever?
- [ ] Backup do original antes de escrever?

## Dependências Já Instaladas

```
pyarrow==23.0.1              # ← Já em requirements.txt
pandas==3.0.1                # ← Já em requirements.txt
```

Parquet é suportado nativamente via `pd.read_parquet()` / `df.to_parquet()`.

## Exemplos de Tarefas Típicas

### **Tarefa 1: Carregar apenas ativos para análise**

```python
import pandas as pd

# Ler só produtos Mix='A' (ativos)
df = pd.read_parquet(
    "bdados/con5cod.parquet",
    columns=['cod_consinco', 'descricao', 'Emb']
)
df = df[df['Mix'] == 'A']
```

### **Tarefa 2: Validar integridade antes de usar**

```python
from pyarrow.parquet import ParquetFile

pf = ParquetFile("bdados/con5cod.parquet")
print(f"Linhas: {pf.num_rows}, Colunas: {pf.num_columns}")
print(f"Schema: {pf.schema}")
```

### **Tarefa 3: Mesclar custom + parquet (padrão ProjetoBak)**

```python
import pandas as pd

df_custom = pd.read_sql("SELECT * FROM produtos_custom", engine)
df_parquet = pd.read_parquet("bdados/con5cod.parquet")

# Custom sempre prevalece
codigos_custom = set(df_custom['cod_consinco'].values)
df_parquet = df_parquet[~df_parquet['cod_consinco'].isin(codigos_custom)]

df_final = pd.concat([df_custom, df_parquet], ignore_index=True)
```

## Integração com Agentes

**Danilo Dados** usa esta skill para:
- Carregar base de produtos/consumo
- Validar integridade de parquet
- Calcular ROP/cobertura sobre parquet

**Ale Governança** usa para:
- Auditar tipos de dados
- Detectar inconsistências
- Documentar schema

**Roberta Relatórios** usa para:
- Agregações de consumo
- Particionamento por período
- Exportação para dashboard

## Referências

- Docs PyArrow: https://arrow.apache.org/docs/python/
- Pandas Parquet: https://pandas.pydata.org/docs/user_guide/io.html#parquet
- `utils/produtos_loader.py`: Exemplo de leitura + mesclagem
- `requirements.txt`: `pyarrow==23.0.1`
