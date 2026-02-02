# ProjetoBak - Versão 2.0.0

Sistema de gestão de produtos e pedidos com integração Consinco.

## 📁 Estrutura do Projeto

```
ProjetoBak/
├── app.py                          # Aplicação principal Streamlit
├── main.py                         # Ponto de entrada da aplicação
├── requirements.txt                # Dependências Python
├── README.md                       # Documentação principal
├── ProjetoPY.code-workspace        # Configuração do workspace
│
├── bdados/                         # Base de dados
│   └── con5cod.parquet            # Produtos Consinco (36k registros)
│
├── page/                           # Módulos de páginas da aplicação
│   ├── home.py                     # Página inicial
│   ├── consulta_mix.py             # 🆕 Consulta de produtos (cod_consinco)
│   ├── pedido_cd.py                # Pedidos por código
│   ├── aprovacao_pedidos.py        # Aprovação de pedidos (admin)
│   ├── admin_uploads.py            # Gerenciamento de uploads (admin)
│   ├── admin_maint.py              # Administração de usuários
│   ├── status_usuarios.py          # Status de usuários online
│   ├── contato.py                  # Sistema de chamados
│   ├── mudar_senha.py              # Alteração de senha
│   ├── area_fornecedor.py          # Área de fornecedores
│   ├── admin_fornecedor.py         # Admin de fornecedores
│   └── contato_fornecedor.py       # Contato fornecedores
│
├── migrations/                     # Scripts de migração (legado)
│   ├── 001_safe_add_columns.sql
│   ├── 002_direct_rename.sql
│   └── run_migration_safe.sh
│
├── scripts/                        # Scripts de manutenção
│   └── smoke_test.py               # Testes automatizados
│
├── tools/                          # Ferramentas auxiliares
│   ├── apply_migration.py          # Aplicar migrações
│   └── find_and_fix_db.py          # Diagnóstico de BD
│
└── doc/                            # Documentação completa
    ├── README_PRINCIPAL.md         # Este arquivo
    ├── ESTRUTURA_ATUALIZADA.md     # Estrutura detalhada v2.0
    ├── MIGRACAO_CONSINCO.md        # Guia de migração
    ├── CHANGELOG.md                # Histórico de versões
    ├── README_MIGRATIONS.md        # Guia de migrações
```

---

## 🚀 Funcionalidades Principais (v2.0.0)

### 🔍 Consulta de Mix de Produtos
- Busca por código Consinco
- Busca por descrição
- Filtros por embalagem e status
- Exportação para CSV
- Visualização de produtos ativos e suspensos

### 📦 Sistema de Pedidos
- Pedidos por código (CD)
- Scanner de código de barras (mobile)
- Aprovação de pedidos (admin)
- Controle por loja

### 👥 Gestão de Usuários
- Múltiplos perfis (user, admin)
- Controle de acesso por loja
- Status online em tempo real
- Sistema de chamados/suporte

### 🗄️ Dados
- Base Consinco: 36.063 produtos
- Colunas: cod_consinco, descricao, transicao, Mix, Emb
- Arquivo: `bdados/con5cod.parquet`

---

## 🔧 Comandos Úteis

### Executar a aplicação:
```bash
streamlit run main.py
```

### Testes automatizados:
```bash
python3 scripts/smoke_test.py
```

### Verificar dados:
```bash
python3 -c "import pandas as pd; df = pd.read_parquet('bdados/con5cod.parquet'); print(df.info())"
```

---

## 📚 Documentação Adicional

- [CHANGELOG.md](CHANGELOG.md) - Histórico de versões
- [MIGRACAO_CONSINCO.md](MIGRACAO_CONSINCO.md) - Guia de migração para v2.0
- [ESTRUTURA_ATUALIZADA.md](ESTRUTURA_ATUALIZADA.md) - Estrutura detalhada
- [README_MIGRATIONS.md](README_MIGRATIONS.md) - Guia de migrações de BD
- [COMO_OBTER_DATABASE_URL.md](COMO_OBTER_DATABASE_URL.md) - Configuração do banco

---

## ⚠️ Funcionalidades Descontinuadas

As seguintes funcionalidades foram removidas na v2.0.0:
- ❌ Sistema de ofertas (upload_ofertas, ver_ofertas)
- ❌ Dashboard online
- ❌ Gestão de promoções (legado)
- ❌ Consulta antiga de estoque (consulta_cd)

---

## 🔄 Migrações (Legado)

Os scripts de migração estão mantidos para referência histórica mas não são mais necessários para a operação atual do sistema.

Para informações sobre migrações antigas, consulte [README_MIGRATIONS.md](README_MIGRATIONS.md).

---

**Versão:** 2.0.0  
**Última Atualização:** 02/02/2026
