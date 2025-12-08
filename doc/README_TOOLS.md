# 🛠️ Ferramentas e Scripts Auxiliares

Esta pasta contém scripts de manutenção, diagnóstico e ferramentas auxiliares do projeto.

## 📁 Conteúdo

### Scripts de Diagnóstico e Correção

- **`diagnose_ofertas.py`** - Script principal de diagnóstico e correção automática da tabela ofertas
  - Verifica estrutura da tabela
  - Aplica migração automaticamente se necessário
  - Valida a correção

- **`apply_migration.py`** - Script simplificado para aplicar migração
  
- **`check_and_fix_ofertas.py`** - Script interativo de verificação

- **`fix_ofertas_quick.sh`** - Script bash para execução rápida com verificação de pré-requisitos

### Documentação

- **`CORRECAO_OFERTAS.md`** - Guia completo de correção do erro "codigo_interno does not exist"
- **`COMO_OBTER_DATABASE_URL.md`** - Instruções para obter a DATABASE_URL

### Backups

- `backup_before_migration_*.dump` - Backups do banco de dados antes de migrações
- `main.py.bak` - Backup de arquivos anteriores

## 🚀 Uso Rápido

Para corrigir problemas com a tabela ofertas:

```bash
# Opção 1: Script bash (verifica dependências)
./tools/fix_ofertas_quick.sh

# Opção 2: Script Python direto
python3 tools/diagnose_ofertas.py
```

**Requisito:** A variável `DATABASE_URL` deve estar definida no ambiente.

## 📚 Documentação Principal

- Para estrutura do projeto: ver `README.md` na raiz
- Para migrações de banco: ver `migrations/README.md`
