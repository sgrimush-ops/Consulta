# 🛠️ Ferramentas do ProjetoBak

Este diretório contém ferramentas de manutenção e administração do sistema.

---

## 📋 Ferramentas Disponíveis

### 🧹 cleanup_database_v2.py
**Limpeza completa e segura do banco de dados**

Remove dados obsoletos do sistema antigo e prepara o banco para a versão 2.0.0.

**Uso básico:**
```bash
# Testar sem modificar (recomendado)
python3 tools/cleanup_database_v2.py --dry-run

# Executar limpeza real
python3 tools/cleanup_database_v2.py
```

**O que faz:**
- ✅ Remove TODOS os registros da tabela `ofertas`
- ✅ Remove pedidos aprovados antigos (>90 dias)
- ✅ Remove tabelas obsoletas
- ✅ Cria backup automático
- ✅ Otimiza o banco (VACUUM ANALYZE)

**Documentação:** [doc/GUIA_LIMPEZA_BD.md](../doc/GUIA_LIMPEZA_BD.md)

---

### 🔄 apply_migration.py
**Aplicação de migrações SQL no banco de dados**

Executa scripts de migração de forma controlada.

**Uso:**
```bash
python3 tools/apply_migration.py migrations/001_safe_add_columns.sql
```

---

### 🔍 find_and_fix_db.py
**Diagnóstico e correção de problemas no banco**

Ferramenta de diagnóstico para identificar e corrigir problemas comuns.

**Uso:**
```bash
python3 tools/find_and_fix_db.py
```

---

## 📦 Diretório de Backups

### backups/
Armazena backups automáticos criados pela ferramenta de limpeza.

**Formato dos arquivos:**
```
backup_before_cleanup_YYYYMMDD_HHMMSS.sql
```

**Restaurar um backup:**
```bash
psql $DATABASE_URL < tools/backups/backup_before_cleanup_20260202_140530.sql
```

---

## ⚠️ Avisos Importantes

### Antes de Usar Qualquer Ferramenta:

1. **Backup:** Sempre faça backup antes de modificar o banco
2. **Teste:** Use modo `--dry-run` quando disponível
3. **Ambiente:** Confirme que está no ambiente correto
4. **Usuários:** Avise outros usuários antes de operações críticas

### Configuração Necessária:

```bash
export DATABASE_URL='postgresql://user:pass@host:5432/db'
```

---

## 📚 Documentação Relacionada

- [GUIA_LIMPEZA_BD.md](../doc/GUIA_LIMPEZA_BD.md) - Guia completo de limpeza
- [CHANGELOG.md](../doc/CHANGELOG.md) - Histórico de versões
- [MIGRACAO_CONSINCO.md](../doc/MIGRACAO_CONSINCO.md) - Guia de migração
- [README_MIGRATIONS.md](../doc/README_MIGRATIONS.md) - Guia de migrações

---

## 🆘 Suporte

Para problemas ou dúvidas sobre as ferramentas:

1. Consulte a documentação específica
2. Verifique os logs de erro
3. Abra um chamado no sistema de suporte

---

**Versão das Ferramentas:** 2.0.0  
**Última Atualização:** 02/02/2026
