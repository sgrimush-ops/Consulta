# Migrações de Colunas — Padronização de Nomes

Este diretório contém scripts para migrar os nomes de colunas do banco para a nova padronização usada pela aplicação:

- cod_interno (substitui codigo/codigo_interno)
- descricao (substitui produto)
- codigo_ean (substitui ean)

ATENÇÃO: antes de rodar qualquer script em produção, sempre execute em um ambiente de teste/staging e faça backup completo do banco.

Files:
 - 001_safe_add_columns.sql — Migração segura (cria colunas novas, copia dados). Recomendado para produção.
- 001_safe_add_columns_rollback.sql — Reversão para o script seguro.
- 002_direct_rename.sql — Migração direta (renomeia colunas no lugar). Mais rápida, porém de maior risco. Use somente em janela de manutenção.
- 002_direct_rename_rollback.sql — Reversão para o rename direto.

Recomendações de procedimento (safest path):
1. Executar 001_safe_add_columns.sql em staging. Validar a aplicação (apontar o app para staging e rodar testes).
2. Ajustar a aplicação para escrever nas novas colunas (`cod_interno`, `descricao`, `codigo_ean`). Faça deploy e execute em modo compatível (leitura de ambas colunas, se necessário).
3. Quando estiver seguro, e após monitorar por alguns deploys com apenas leitura/escrita nos novos campos, executar um curto processo de universo:
   - Se preferir manter compatibilidade máxima, mantenha colunas antigas por mais tempo; ou
   - Se quiser simplificar o schema, depois de validar, execute uma migração final para remover as colunas antigas e ajustar constraints/indexes.

Direct rename path (single-step, riskier):
Notes about indexes and CONCURRENTLY:
- The safe script attempts to create the unique index inside the transaction. PostgreSQL does NOT allow CREATE INDEX CONCURRENTLY inside a transaction block.
- If you have very large tables and wish to avoid exclusive locks, run the index creation step outside of a transaction using:

   CREATE UNIQUE INDEX CONCURRENTLY uniq_ofertas_cod_period ON ofertas (cod_interno, data_inicio, data_final);

   (Run the above AFTER executing the safe migration and after committing it. That ensures new columns exist before creating index concurrently.)

1. Fazer backup + downtime.
2. Executar 002_direct_rename.sql.
3. Atualizar dependências e validações.

Rollback:
- Os arquivos *_rollback.sql fornecem os passos para desdobrar a alteração. Teste os rollbacks em staging antes de usar em produção.

Se quiser, eu gero scripts `ALTER TABLE` adicionais para recriar índices, constraints nomeados e backups em uma transação mais robusta (com checks extra).
