# ProjetoBak

Este repositório contém a aplicação (Streamlit) e scripts de migração/rotina para gestão de promoções e pedidos.

## Rotina diária: limpeza de ofertas antigas
Para manter o banco enxuto, delete ofertas com `data_final` mais antiga que 1 dia:

- Script: `scripts/cleanup_old_ofertas.py`
- Requer: variável de ambiente `DATABASE_URL` (PostgreSQL)
- Parâmetro opcional: `CLEANUP_OLDER_THAN_DAYS` (padrão: `1`)

Execução manual:

```bash
export DATABASE_URL='postgresql://user:pass@host:5432/dbname'
# Opcional: export CLEANUP_OLDER_THAN_DAYS=1
python scripts/cleanup_old_ofertas.py
```

Agendamento via cron (exemplo às 03:00 todos os dias):

```cron
0 3 * * * /workspaces/ProjetoBak/.venv/bin/python /workspaces/ProjetoBak/scripts/cleanup_old_ofertas.py >> /var/log/cleanup_old_ofertas.log 2>&1
```

Observação: a página `ver_ofertas` também executa uma limpeza leve ao ser acessada, removendo ofertas com `data_final` > 1 dia no passado. O script acima garante a rotina mesmo sem acesso à página.

## Migrações
- Use `migrations/run_migration_safe.sh` com `DATABASE_URL` configurado para criar colunas canônicas (`codigo_interno`, `descricao`, `codigo_ean`) e validar.
- `migrations/001_safe_add_columns.sql` e rollback correspondente.
- `migrations/002_direct_rename.sql` (maior risco) e rollback para renomes diretos.

Criação de índice não bloqueante (opcional):

```bash
./migrations/run_migration_safe.sh --concurrent
```

## Convenções de colunas
- `codigo_interno` (canônico)
- `descricao` (nome do produto)
- `codigo_ean` (EAN)
