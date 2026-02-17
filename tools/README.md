# Ferramentas do ProjetoBak

Este diretorio contem ferramentas de manutencao e administracao do sistema.

---

## Ferramentas disponiveis

### cleanup_database_v2.py
Limpeza completa e segura do banco de dados.

Uso basico:
```bash
# Testar sem modificar (recomendado)
python3 tools/cleanup_database_v2.py --dry-run

# Executar limpeza real
python3 tools/cleanup_database_v2.py
```

O que faz:
- Remove todos os registros da tabela `ofertas`
- Remove pedidos aprovados antigos (>90 dias)
- Remove tabelas obsoletas
- Cria backup automatico
- Otimiza o banco (VACUUM ANALYZE)

Documentacao: [doc/GUIA_LIMPEZA_BD.md](../doc/GUIA_LIMPEZA_BD.md)

---

### cleanup_pedidos_antigos.py
Limpeza de pedidos antigos com opcao de dry-run.

Uso:
```bash
python3 tools/cleanup_pedidos_antigos.py --dry-run
```

---

### verify_produtos_integrity.py
Verificacao de integridade dos dados de produtos.

Uso:
```bash
python3 tools/verify_produtos_integrity.py
```

---

## Diretorio de backups

### backups/
Armazena backups automaticos criados pela ferramenta de limpeza.

Formato dos arquivos:
```
backup_before_cleanup_YYYYMMDD_HHMMSS.sql
```

Restaurar um backup:
```bash
psql $DATABASE_URL < tools/backups/backup_before_cleanup_20260202_140530.sql
```

---

## Avisos importantes

### Antes de usar qualquer ferramenta:

1. Backup: sempre faca backup antes de modificar o banco
2. Teste: use modo `--dry-run` quando disponivel
3. Ambiente: confirme que esta no ambiente correto
4. Usuarios: avise outros usuarios antes de operacoes criticas

### Configuracao necessaria:

```bash
export DATABASE_URL='postgresql://user:pass@host:5432/db'
```

---

## Documentacao relacionada

- [GUIA_LIMPEZA_BD.md](../doc/GUIA_LIMPEZA_BD.md) - Guia completo de limpeza
- [CHANGELOG.md](../doc/CHANGELOG.md) - Historico de versoes
- [MIGRACAO_CONSINCO.md](../doc/MIGRACAO_CONSINCO.md) - Guia de migracao (legado)
- [README_MIGRATIONS.md](../doc/README_MIGRATIONS.md) - Guia de migracoes (legado)

---

## Suporte

Para problemas ou duvidas sobre as ferramentas:

1. Consulte a documentacao especifica
2. Verifique os logs de erro
3. Abra um chamado no sistema de suporte

---

**Versao das ferramentas:** 2.0.0  
**Ultima atualizacao:** 17/02/2026
