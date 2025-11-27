# 🔧 SOLUÇÃO RÁPIDA: Erro "codigo_interno does not exist"

## ⚠️ Problema

A aplicação está tentando usar `codigo_interno` mas o banco tem `codigo`.

## ✅ Solução em 3 Passos

### 1️⃣ Obtenha sua DATABASE_URL

A DATABASE_URL é a string de conexão com seu banco PostgreSQL.

**Se você está usando Render.com ou Heroku:**
- Acesse o painel do seu banco de dados
- Copie a "Internal Database URL" ou "DATABASE_URL"
- Ela se parece com: `postgresql://usuario:senha@host.region.render.com:5432/nome_banco`

**Se você está rodando localmente:**
```
postgresql://postgres:sua_senha@localhost:5432/nome_banco
```

### 2️⃣ Execute o Script de Correção

**Opção A - Dentro do Streamlit (MAIS FÁCIL - Recomendado):**

1. Abra o arquivo `page/upload_ofertas.py`
2. Adicione estas linhas NO INÍCIO do arquivo (linha 1):

```python
from tools.fix_ofertas_streamlit import fix_ofertas_table
from app import get_engine
import streamlit as st

# Correção temporária
engine = get_engine()
fix_ofertas_table(engine)
st.stop()  # Para aqui para fazer a correção
```

3. Execute a aplicação Streamlit normalmente
4. Acesse a página "Upload de Ofertas"
5. Clique no botão "🔧 Aplicar Correção Agora"
6. Após o sucesso, **REMOVA** essas linhas que você adicionou
7. Recarregue a aplicação

**Opção B - Script Interativo:**
```bash
cd /workspaces/ProjetoBak
python3 tools/fix_ofertas_interactive.py
```
O script irá pedir sua DATABASE_URL e aplicar a correção automaticamente.

**Opção C - Com Variável de Ambiente:**
```bash
export DATABASE_URL='cole_sua_url_aqui'
python3 tools/fix_ofertas_now.py
```

**Opção D - Direto no PostgreSQL (se tiver psql):**
```bash
export DATABASE_URL='cole_sua_url_aqui'
psql $DATABASE_URL -f migrations/002_direct_rename.sql
```

### 3️⃣ Teste a Aplicação

Após executar a correção, teste fazendo upload de ofertas novamente.

---

## 🆘 Ainda com Problemas?

### Verificar se a migração funcionou:

```bash
export DATABASE_URL='sua_url'
python3 -c "
from sqlalchemy import create_engine, inspect
import os

db_url = os.getenv('DATABASE_URL')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

engine = create_engine(db_url, connect_args={'sslmode': 'require'})
inspector = inspect(engine)

print('Colunas da tabela ofertas:')
for col in inspector.get_columns('ofertas'):
    print(f\"  ✓ {col['name']}\")
"
```

Você deve ver `codigo_interno` e `descricao` na lista.

### DATABASE_URL não funciona?

Verifique:
1. ✅ URL começa com `postgresql://` (não `postgres://`)
2. ✅ Credenciais estão corretas
3. ✅ Host e porta estão acessíveis
4. ✅ Banco de dados existe

### Teste de conexão rápido:

```bash
export DATABASE_URL='sua_url'
python3 -c "
from sqlalchemy import create_engine
import os

db_url = os.getenv('DATABASE_URL')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

try:
    engine = create_engine(db_url, connect_args={'sslmode': 'require'})
    with engine.connect() as conn:
        print('✓ Conexão OK!')
except Exception as e:
    print(f'❌ Erro: {e}')
"
```

---

## 📞 Informações Técnicas

**O que a migração faz:**
- Renomeia `codigo` → `codigo_interno`
- Renomeia `produto` → `descricao`
- Atualiza constraints relacionadas

**Arquivo de migração:**
`migrations/002_direct_rename.sql`

**Backup:**
A migração inclui transação. Em caso de erro, nada é alterado.

**Rollback (se necessário):**
```bash
psql $DATABASE_URL -f migrations/002_direct_rename_rollback.sql
```

---

**Atualizado em:** 27 de novembro de 2025
