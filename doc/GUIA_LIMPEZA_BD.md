# 🧹 Guia de Limpeza do Banco de Dados - v2.0.0

## 📋 Visão Geral

Este guia explica como limpar o banco de dados da nuvem, removendo dados obsoletos do sistema antigo e preparando para a nova estrutura Consinco.

---

## 🛠️ Ferramenta: cleanup_database_v2.py

### O que o script faz:

1. **Cria backup automático** antes de qualquer modificação
2. **Remove TODOS os registros** da tabela `ofertas`
3. **Remove pedidos aprovados antigos** (mais de 90 dias por padrão)
4. **Remove tabelas obsoletas** (mix_produtos, estoque_cd)
5. **Otimiza o banco** com VACUUM ANALYZE

### O que é preservado:

✅ Tabela `users` (usuários do sistema)  
✅ Tabela `pedidos_consolidados` (pedidos recentes)  
✅ Tabela `contato_chamados` e `contato_mensagens` (sistema de suporte)  
✅ Tabela `fornecedores_users` (usuários fornecedores)

---

## 🚀 Como Usar

### 1. Teste Primeiro (Dry-Run)

**Sempre execute em modo dry-run primeiro para ver o que será feito:**

```bash
# Configure a DATABASE_URL
export DATABASE_URL='postgresql://user:pass@host:5432/dbname'

# Execute em modo dry-run (não faz modificações)
python3 tools/cleanup_database_v2.py --dry-run
```

**Saída esperada:**
```
╔══════════════════════════════════════════════════════════════╗
║          LIMPEZA DO BANCO DE DADOS - v2.0.0                  ║
╚══════════════════════════════════════════════════════════════╝

⚠️  MODO DRY-RUN: Nenhuma modificação será feita

🔌 Conectando ao banco de dados...
✅ Conexão estabelecida com sucesso!

📊 Tabelas encontradas no banco de dados:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📋 contato_chamados                          5 registros
  📋 contato_mensagens                        12 registros
  📋 ofertas                                 450 registros
  📋 pedidos_consolidados                    127 registros
  📋 users                                     8 registros
  📋 fornecedores_users                        3 registros
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🗑️  LIMPEZA: Tabela 'ofertas'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Registros atuais: 450
  [DRY-RUN] Seria deletado: 450 registros

🗑️  LIMPEZA: Pedidos aprovados com mais de 90 dias
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Pedidos aprovados antigos encontrados: 34
  [DRY-RUN] Seria deletado: 34 registros

🗑️  REMOÇÃO: Tabelas obsoletas
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ℹ️  Tabela mix_produtos não existe
  ℹ️  Tabela estoque_cd não existe

⚡ OTIMIZAÇÃO: Limpeza e análise do banco
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [DRY-RUN] Seria executado: VACUUM ANALYZE

✅ DRY-RUN CONCLUÍDO - Nenhuma modificação foi feita
```

---

### 2. Executar a Limpeza Real

**Depois de verificar que está tudo correto, execute a limpeza real:**

```bash
# ATENÇÃO: Isto fará mudanças permanentes!
python3 tools/cleanup_database_v2.py
```

**O script irá:**
1. Mostrar o estado atual do banco
2. Criar um backup automático
3. Pedir confirmação com "CONFIRMO"
4. Executar todas as limpezas
5. Mostrar estatísticas finais

---

## ⚙️ Opções Disponíveis

### --dry-run
Executa sem fazer modificações (recomendado primeiro)
```bash
python3 tools/cleanup_database_v2.py --dry-run
```

### --no-backup
**NÃO RECOMENDADO!** Pula a criação do backup
```bash
python3 tools/cleanup_database_v2.py --no-backup
```

### --keep-pedidos-days N
Define quantos dias de pedidos manter (padrão: 90)
```bash
# Manter apenas últimos 30 dias
python3 tools/cleanup_database_v2.py --keep-pedidos-days 30

# Manter últimos 180 dias
python3 tools/cleanup_database_v2.py --keep-pedidos-days 180
```

---

## 📦 Backups

### Localização dos Backups

Os backups são salvos em:
```
tools/backups/backup_before_cleanup_YYYYMMDD_HHMMSS.sql
```

### Restaurar um Backup

Se precisar restaurar:

```bash
# Restaurar backup
psql $DATABASE_URL < tools/backups/backup_before_cleanup_20260202_140530.sql
```

---

## ⚠️ Avisos Importantes

### 🔴 ATENÇÃO

1. **Sempre execute --dry-run primeiro**
2. **Verifique que tem um backup válido**
3. **Confirme que está no ambiente correto**
4. **A operação é irreversível**

### ✅ Checklist Antes de Executar

- [ ] Executei em modo --dry-run
- [ ] Verifiquei quais dados serão removidos
- [ ] Confirmei que estou no banco correto
- [ ] Tenho backup ou aceito perder os dados
- [ ] Avisei outros usuários do sistema

---

## 🎯 Resultados Esperados

### Antes da Limpeza:
```
📊 ESTATÍSTICAS
  📋 ofertas                          450 registros
  📋 pedidos_consolidados            127 registros
  📋 users                             8 registros
  📋 contato_chamados                  5 registros
```

### Após a Limpeza:
```
📊 ESTATÍSTICAS FINAIS
  📋 ofertas                            0 registros ✅
  📋 pedidos_consolidados              93 registros ✅
  📋 users                              8 registros ✅
  📋 contato_chamados                   5 registros ✅
```

---

## 🆘 Solução de Problemas

### Erro: DATABASE_URL não configurada

```bash
export DATABASE_URL='postgresql://user:pass@host:5432/dbname'
```

### Erro: pg_dump não encontrado

Instale o cliente PostgreSQL:
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-client

# macOS
brew install postgresql
```

### Erro de conexão

Verifique:
1. URL está correta
2. Servidor está acessível
3. Credenciais estão válidas
4. Porta está aberta

### Backup falhou

Use `--no-backup` apenas se:
- Já tem backup manual
- Está em ambiente de teste
- Aceita o risco de perder dados

---

## 📝 Logs e Auditoria

O script gera saída detalhada que pode ser salva:

```bash
# Salvar log completo
python3 tools/cleanup_database_v2.py 2>&1 | tee cleanup_log.txt

# Salvar apenas resultado
python3 tools/cleanup_database_v2.py > cleanup_result.txt 2>&1
```

---

## 🔄 Próximos Passos

Após a limpeza:

1. ✅ Verificar estatísticas finais
2. ✅ Testar aplicação
3. ✅ Verificar funcionalidades principais
4. ✅ Monitorar performance
5. ✅ Arquivar backups antigos

---

## 📞 Suporte

Para problemas ou dúvidas:
- Consulte [CHANGELOG.md](CHANGELOG.md)
- Veja [MIGRACAO_CONSINCO.md](MIGRACAO_CONSINCO.md)
- Abra um chamado no sistema

---

**Versão:** 2.0.0  
**Data:** 02/02/2026  
**Status:** ✅ Pronto para uso
