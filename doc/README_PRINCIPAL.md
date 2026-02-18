# ProjetoBak - Versao 2.0.0

Sistema de gestao de produtos, pedidos e usuarios com integracao Consinco.

## Estrutura do projeto

```
ProjetoBak/
├── app.py                   # Aplicacao principal (funcionarios)
├── main.py                  # Menu principal e acesso fornecedor
├── requirements.txt         # Dependencias Python
├── README.md                # Documentacao principal
├── ProjetoPY.code-workspace # Configuracao do workspace
│
├── bdados/                  # Base de dados local
│   └── con5cod.parquet       # Produtos Consinco (36k registros)
│
├── page/                    # Modulos de paginas
│   ├── home.py               # Pagina inicial
│   ├── consulta_mix.py       # Consulta de produtos (cod_consinco)
│   ├── pedido_cd.py          # Pedidos por codigo
│   ├── pedido_consumo.py     # Pedidos de consumo
│   ├── aprovacao_pedidos.py  # Aprovacao de pedidos (admin)
│   ├── admin_uploads.py      # Gerenciamento de uploads (admin)
│   ├── admin_maint.py        # Administracao de usuarios
│   ├── status_usuarios.py    # Status de usuarios online
│   ├── contato.py            # Sistema de chamados
│   ├── mudar_senha.py        # Alteracao de senha
│   ├── area_fornecedor.py    # Area de fornecedores
│   ├── admin_fornecedor.py   # Admin de fornecedores
│   └── contato_fornecedor.py # Contato fornecedores
│
├── scripts/                 # Scripts auxiliares
│   └── smoke_test.py         # Testes automatizados
│
├── tools/                   # Ferramentas de manutencao
│   ├── cleanup_database_v2.py
│   └── cleanup_pedidos_antigos.py
│
├── utils/                   # Utilitarios compartilhados
│   └── timezone.py           # Relogio padrao de Brasilia
│
└── doc/                     # Documentacao completa
    ├── README_PRINCIPAL.md  # Este arquivo
    ├── MIGRACAO_CONSINCO.md # Guia de migracao (legado)
    ├── CHANGELOG.md         # Historico de versoes
    ├── README_MIGRATIONS.md # Guia de migracoes (legado)
    ├── GUIA_LIMPEZA_BD.md   # Limpeza do banco
    └── COMO_OBTER_DATABASE_URL.md
```

## Funcionalidades principais

### Consulta de mix de produtos
- Busca por codigo Consinco e descricao
- Filtros por embalagem e status
- Exportacao para CSV

### Sistema de pedidos
- Pedido por codigo (CD)
- Pedido de consumo
- Aprovacao de pedidos (admin)
- Controle por lojas

### Gestao de usuarios
- Perfis: user e admin
- Cargo do usuario
- Controle de acesso por loja
- Status online em tempo real
- Sistema de chamados/suporte

### Area de fornecedores
- Login separado para fornecedor/promotor
- Pagina inicial e contato/suporte
- Administracao de fornecedores (admin_fornecedor)

### Dados
- Base Consinco em bdados/con5cod.parquet
- Colunas: cod_consinco, descricao, transicao, Mix, Emb

## Comandos uteis

### Executar a aplicacao
```bash
streamlit run main.py
```

### Testes automatizados
```bash
python3 scripts/smoke_test.py
```

### Verificar dados
```bash
python3 -c "import pandas as pd; df = pd.read_parquet('bdados/con5cod.parquet'); print(df.info())"
```

## Documentacao adicional

- [CHANGELOG.md](CHANGELOG.md) - Historico de versoes
- [MIGRACAO_CONSINCO.md](MIGRACAO_CONSINCO.md) - Guia de migracao (legado)
- [README_MIGRATIONS.md](README_MIGRATIONS.md) - Migrações (legado)
- [GUIA_LIMPEZA_BD.md](GUIA_LIMPEZA_BD.md) - Limpeza do banco
- [COMO_OBTER_DATABASE_URL.md](COMO_OBTER_DATABASE_URL.md) - Configuracao do banco

**Versao:** 2.0.2
**Ultima atualizacao:** 18/02/2026
