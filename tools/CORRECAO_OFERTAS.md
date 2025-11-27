# 🔧 Correção do Erro: "column codigo_interno does not exist"

## 📋 Problema

A aplicação está tentando inserir dados na tabela `ofertas` usando a coluna `codigo_interno`, mas o banco de dados ainda possui a coluna com o nome antigo `codigo`.

**Erro completo:**
```
psycopg2.errors.UndefinedColumn: column "codigo_interno" of relation "ofertas" does not exist
```

## 🔍 Causa

A migração de renomeação de colunas (`002_direct_rename.sql`) não foi aplicada ao banco de dados. Esta migração renomeia:
- `codigo` → `codigo_interno`
- `produto` → `descricao`

## ✅ Solução

### Opção 1: Script Automático (Recomendado)

Execute o script de diagnóstico que verifica e corrige automaticamente:

```bash
python diagnose_ofertas.py
```

Este script irá:
1. Verificar se a `DATABASE_URL` está definida
2. Checar a estrutura atual da tabela `ofertas`
3. Aplicar a migração se necessário
4. Validar que a correção foi bem-sucedida

### Opção 2: Aplicação Manual da Migração

Se preferir aplicar manualmente:

```bash
python apply_migration.py
```

### Opção 3: Execução Direta do SQL

Se tiver acesso direto ao PostgreSQL:

```bash
psql $DATABASE_URL -f migrations/002_direct_rename.sql
```

## 📝 Pré-requisitos

### 1. Variável de Ambiente DATABASE_URL

A `DATABASE_URL` deve estar definida. Verifique com:

```bash
echo $DATABASE_URL
```

Se não estiver definida, configure-a:

**Para sessão atual:**
```bash
export DATABASE_URL='postgresql://user:password@host:port/database'
```

**Para tornar permanente (adicione ao ~/.bashrc):**
```bash
echo 'export DATABASE_URL="postgresql://user:password@host:port/database"' >> ~/.bashrc
source ~/.bashrc
```

**Ou use arquivo .env:**
```bash
# Crie um arquivo .env na raiz do projeto
echo 'DATABASE_URL=postgresql://user:password@host:port/database' > .env

# Carregue as variáveis
source .env
```

### 2. Backup do Banco de Dados

⚠️ **IMPORTANTE:** Antes de aplicar qualquer migração, faça backup!

```bash
# Se tiver pg_dump instalado
pg_dump $DATABASE_URL > backup_antes_migracao_$(date +%Y%m%d_%H%M%S).dump

# Ou use o script Python (se disponível)
python -c "import os; from datetime import datetime; os.system(f'pg_dump {os.getenv(\"DATABASE_URL\")} > backup_{datetime.now().strftime(\"%Y%m%d_%H%M%S\")}.dump')"
```

## 🔍 Verificação Manual

Para verificar manualmente a estrutura da tabela:

```bash
# Via Python
python -c "
import os
from sqlalchemy import create_engine, inspect

db_url = os.getenv('DATABASE_URL')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

engine = create_engine(db_url, connect_args={'sslmode': 'require'})
inspector = inspect(engine)

print('Colunas da tabela ofertas:')
for col in inspector.get_columns('ofertas'):
    print(f'  - {col[\"name\"]} ({col[\"type\"]})')
"
```

## 📊 Estrutura Esperada

Após a migração, a tabela `ofertas` deve ter:

```
✓ codigo_interno (INTEGER ou TEXT)
✓ descricao (TEXT)
✓ oferta (NUMERIC)
✓ data_inicio (DATE)
✓ data_final (DATE)
```

## 🐛 Troubleshooting

### Erro: "DATABASE_URL não encontrada"
- Verifique se a variável está definida: `echo $DATABASE_URL`
- Defina conforme instruções na seção de pré-requisitos

### Erro: "Tabela ofertas não existe"
- O banco de dados pode não estar inicializado
- Execute a aplicação uma vez para criar as tabelas base
- Verifique se está conectando ao banco correto

### Erro: "Permission denied"
- Verifique se o usuário do banco tem permissão para ALTER TABLE
- Pode precisar de permissões de administrador

### Migração executada mas erro persiste
1. Verifique se há cache: reinicie a aplicação
2. Confirme que está usando a mesma DATABASE_URL
3. Verifique se não há múltiplas instâncias do banco

## 📚 Arquivos Relacionados

- `diagnose_ofertas.py` - Script de diagnóstico e correção automática
- `apply_migration.py` - Script simplificado de migração
- `check_and_fix_ofertas.py` - Script interativo de verificação
- `migrations/002_direct_rename.sql` - Arquivo SQL de migração
- `migrations/002_direct_rename_rollback.sql` - Rollback se necessário

## 🔄 Rollback

Se precisar reverter a migração:

```bash
psql $DATABASE_URL -f migrations/002_direct_rename_rollback.sql
```

⚠️ **Atenção:** O rollback só funciona se as colunas antigas ainda existirem no banco.

## 📞 Suporte

Se o problema persistir:
1. Execute `python diagnose_ofertas.py` e compartilhe o output completo
2. Verifique os logs da aplicação
3. Confirme a versão do PostgreSQL: `psql $DATABASE_URL -c "SELECT version();"`

---

**Última atualização:** 27 de novembro de 2025
