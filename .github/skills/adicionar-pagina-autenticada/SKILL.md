# Skill: Adicionar Página Autenticada no Streamlit

## Contexto do ProjetoBak

O ProjetoBak é uma aplicação Streamlit com arquitetura **multi-página baseada em roteamento por `.session_state`**. O fluxo de autenticação e navegação segue um padrão específico:

- **Entrada principal:** `main.py` (login: baklizi ou fornecedor)
- **Orquestrador:** `app.py` (inicializa banco, roteamento de páginas)
- **Páginas:** `page/*.py` (componentes importados dinamicamente)
- **Banco:** PostgreSQL com tabelas `users` e `fornecedores_users` (role-based)

## Padrão Arquitetural de Páginas

Cada página segue a estrutura:

```python
# page/minha_nova_pagina.py
import streamlit as st
from sqlalchemy import text

def show_minha_nova_pagina(engine, base_data_path):
    """Descrição da página. engine: SQLAlchemy Engine; base_data_path: str."""
    
    # 1. Validar acesso (role/lojas)
    user = st.session_state.get("username", "Anônimo")
    role = st.session_state.get("role", "user")
    lojas = st.session_state.get("lojas_acesso", [])
    
    # 2. Restringir acesso (se necessário)
    if role not in ["admin", "vendedor"]:
        st.error("Acesso restrito.")
        return
    
    # 3. Renderizar conteúdo
    st.title("Minha Nova Página")
    st.write("Conteúdo aqui...")
    
    # 4. Interações com banco (se necessário)
    # query = text("SELECT * FROM produtos WHERE loja IN (:lojas)")
    # with engine.connect() as conn:
    #     result = conn.execute(query, {"lojas": tuple(lojas)})
```

## Passos para Adicionar Nova Página

### 1. **Criar arquivo da página** (`page/nova_pagina.py`)
   - Nome deve ser único e descritivo
   - Função principal: `show_nova_pagina(engine, base_data_path)`
   - Implementar validação de role/lojas usando `st.session_state`

### 2. **Importar em `app.py`**
   ```python
   from page.nova_pagina import show_nova_pagina
   ```

### 3. **Adicionar ao dicionário de rotas em `app.py`**
   ```python
   pages = {
       "Home": lambda: show_home_page(engine, BASE_DATA_PATH),
       "Nova Página": lambda: show_nova_pagina(engine, BASE_DATA_PATH),
       # ... outras páginas
   }
   ```

### 4. **Adicionar atalho em `page/home.py` (se necessário)**
   ```python
   if role == "admin":
       menu_options["🆕 Nova Página"] = "Nova Página"
   ```

## Checklist de Validação

- [ ] Arquivo criado em `page/nova_pagina.py`
- [ ] Função `show_nova_pagina(engine, base_data_path)` definida
- [ ] Validação de `role` ou `lojas_acesso` implementada
- [ ] Importado em `app.py` com statement `from page.nova_pagina import show_nova_pagina`
- [ ] Adicionado ao dicionário `pages` em `app.py` com chave e lambda
- [ ] Testado: página acessível após autenticação com role correto
- [ ] Testado: acesso negado se role/lojas insuficientes

## Padrões Reutilizáveis

### Acesso ao usuário logado
```python
user = st.session_state.get("username", "")
role = st.session_state.get("role", "user")
lojas = st.session_state.get("lojas_acesso", [])
```

### Restrição por role
```python
if role != "admin":
    st.error("Apenas administradores podem acessar esta página.")
    return
```

### Query ao banco
```python
from sqlalchemy import text

with engine.connect() as conn:
    query = text("SELECT * FROM tabela WHERE loja = :loja")
    result = conn.execute(query, {"loja": lojas[0]})
    df = pd.read_sql(query, conn)
```

### Armazenamento de dados no `session_state`
```python
if "meu_estado" not in st.session_state:
    st.session_state["meu_estado"] = valor_inicial

# Usar depois
if st.session_state["meu_estado"]:
    st.write("Atualizado!")
```

## Exemplo Prático: Página de Relatório

```python
# page/relatorio_vendas.py
import streamlit as st
import pandas as pd
from sqlalchemy import text

def show_relatorio_vendas(engine, base_data_path):
    """Relatório de vendas por loja (apenas para admin)."""
    
    # Validação
    role = st.session_state.get("role", "user")
    lojas = st.session_state.get("lojas_acesso", [])
    
    if role != "admin" and not lojas:
        st.error("Você não tem permissão para acessar relatórios.")
        return
    
    st.title("📊 Relatório de Vendas")
    
    # Filtro de loja
    loja_selecionada = st.selectbox("Selecione uma loja:", lojas or ["001"])
    
    # Query
    query = text("""
        SELECT data, produto, quantidade, valor
        FROM pedidos_consolidados
        WHERE loja_id = :loja
        ORDER BY data DESC
        LIMIT 100
    """)
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"loja": loja_selecionada})
            st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
```

## Integração com Agentes

Agentes como **Anton (Software Engineer)** e **Ale (Data Governance)** usam esta skill para:
- **Criar nova página** respeitando padrão de segurança
- **Validar** que página foi integrada corretamente
- **Documentar** a página no README/API
- **Testar** acesso com diferentes roles

## Referências

- `app.py` linhas 15-50: Importações e dicionário de páginas
- `page/home.py` linhas 25-55: Menu dinâmico baseado em role
- `main.py` linhas 160-185: Fluxo de autenticação Baklizi
- `doc/AGENTES_SQUADS_SKILLS.md`: Guia geral de integração IA
