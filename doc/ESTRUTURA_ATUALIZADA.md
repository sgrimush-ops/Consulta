# Estrutura do Sistema - Versão 2.0.0

## 📁 Estrutura de Diretórios

```
ProjetoBak/
├── app.py                      # Aplicação principal Streamlit
├── main.py                     # Ponto de entrada multi-perfil
├── requirements.txt            # Dependências Python
├── README.md                   # Documentação principal
│
├── bdados/                     # 📊 Dados do Sistema
│   └── con5cod.parquet        # Base de produtos (cod_consinco)
│
├── doc/                        # 📚 Documentação
│   ├── CHANGELOG.md           # Histórico de versões
│   ├── MIGRACAO_CONSINCO.md   # Guia de migração
│   ├── ESTRUTURA_ATUALIZADA.md # Este arquivo
│   ├── README_PRINCIPAL.md    # Documentação técnica
│   └── ...
│
├── page/                       # 📄 Páginas do Sistema
│   ├── __init__.py
│   │
│   ├── ✨ PÁGINAS ATIVAS:
│   ├── consulta_mix.py        # 🆕 Consulta de produtos (NOVA)
│   ├── home.py                # Página inicial
│   ├── pedido_cd.py           # Pedidos por código
│   ├── aprovacao_pedidos.py   # Aprovação de pedidos
│   ├── status_usuarios.py     # Status de usuários online
│   ├── mudar_senha.py         # Alteração de senha
│   ├── contato.py             # Sistema de chamados
│   ├── admin_maint.py         # Administração do sistema
│   └── admin_uploads.py       # Gestão de uploads
│
├── scripts/                    # 🔧 Scripts Auxiliares
│   ├── smoke_test.py          # Testes automatizados
│   ├── cleanup_old_ofertas.py
│   └── ...
│
├── tools/                      # 🛠️ Ferramentas
│   ├── diagnose_ofertas.py
│   └── ...
│
└── migrations/                 # 💾 Migrações de BD
    ├── 001_safe_add_columns.sql
    └── ...
```

---

## 🗺️ Fluxo de Páginas

### Entrada do Sistema
```
main.py (Menu Principal)
    ├─→ Baklizi (Funcionários)
    │       └─→ app.py (Sistema Principal)
    │
    └─→ Fornecedor/Promotor
            └─→ Área do Fornecedor
```

### Sistema Principal (app.py)

```
Login
  ↓
Home (Página Inicial)
  ├─→ 🔍 Consulta de Mix (NOVA PÁGINA)
  │      ├─ Busca por Código Consinco
  │      ├─ Busca por Descrição
  │      └─ Visualização Completa
  │
  ├─→ 🔐 Alterar Senha
  │
  ├─→ 💬 Contato
  │      └─ Sistema de Chamados
  │
  ├─→ 🛒 Pedido por Código (CD)
  │      └─ (Apenas para usuários com acesso a lojas)
  │
  └─→ ADMIN (Apenas Administradores)
         ├─ ✅ Aprovação de Pedidos
         ├─ 👥 Status do Usuário
         ├─ ⚙️ Administração
         └─ 📤 Admin Uploads
```

---

## 🎯 Páginas por Perfil de Usuário

### 👤 Usuário Comum
- ✅ Home
- ✅ Consulta de Mix
- ✅ Alterar Senha
- ✅ Contato

### 🏪 Usuário com Acesso a Lojas
- ✅ Tudo do Usuário Comum
- ✅ Pedido por Código (CD)

### 🔧 Administrador
- ✅ Tudo do Usuário com Lojas
- ✅ Aprovação de Pedidos
- ✅ Status do Usuário
- ✅ Administração
- ✅ Admin Uploads

---

## 📊 Dados Principais

### Arquivo: `bdados/con5cod.parquet`

**Estrutura:**
- `cod_consinco` (int64) - Código principal
- `descricao` (string) - Descrição do produto
- `transicao` (int64) - Código antigo
- `Mix` (string) - Status: A=Ativo, S=Suspenso
- `Emb` (int64) - Quantidade da embalagem

**Tamanho:** 36.063 registros

---

## 🗄️ Banco de Dados PostgreSQL

### Tabelas Principais:

#### `users`
- Usuários do sistema
- Roles e permissões
- Controle de acesso por loja

#### `pedidos_consolidados`
- Pedidos realizados
- Status de aprovação
- Distribuição por loja

#### `contato_chamados` e `contato_mensagens`
- Sistema de suporte
- Comunicação usuário-admin

#### `fornecedores_users`
- Usuários fornecedores
- Controle de acesso

#### `ofertas` (OBSOLETA)
- Mantida por compatibilidade
- Não mais utilizada ativamente

---

## 🔄 Fluxo de Dados

### Consulta de Produtos:
```
Usuário → consulta_mix.py → con5cod.parquet → Resultado
```

### Pedidos:
```
Usuário → pedido_cd.py → pedidos_consolidados (BD) → aprovacao_pedidos.py
```

### Suporte:
```
Usuário → contato.py → contato_chamados (BD) → Admin
```

---

## 🚀 Novas Funcionalidades da v2.0.0

### 1. Consulta de Mix Avançada
- ✨ Busca por código Consinco
- ✨ Busca por descrição
- ✨ Filtros por embalagem
- ✨ Exportação CSV
- ✨ Visualização de produtos suspensos

### 2. Menu Simplificado
- Remoção de funcionalidades obsoletas
- Foco em funcionalidades essenciais
- Interface mais limpa

### 3. Integração Consinco
- Novo sistema de códigos
- Mapeamento de códigos antigos
- Dados atualizados

---

## ❌ Funcionalidades Removidas

### Sistema de Ofertas
- `upload_ofertas.py` ❌
- `ver_ofertas.py` ❌
- Gestão de promoções antiga ❌

### Consultas Antigas
- `consulta_cd.py` ❌ → Substituída por `consulta_mix.py` ✅

### Gestão de Promoções Antiga
- `gestao_promo.py` ❌

### Dashboard
- `dashboard_online.py` ❌

---

## 📋 Dependências Principais

```txt
streamlit>=1.31.0
pandas>=2.1.4
sqlalchemy>=2.0.25
psycopg2-binary>=2.9.9
pyarrow>=15.0.0
pyzbar==0.1.9
```

---

## 🔧 Comandos Úteis

### Executar a aplicação:
```bash
streamlit run main.py
```

### Executar testes:
```bash
python3 scripts/smoke_test.py
```

### Verificar estrutura do parquet:
```bash
python3 -c "import pandas as pd; df = pd.read_parquet('bdados/con5cod.parquet'); print(df.info())"
```

---

**Última Atualização:** 02/02/2026  
**Versão:** 2.0.0
