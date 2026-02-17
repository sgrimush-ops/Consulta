# ProjetoBak - Gestão de Produtos

Sistema de gestão de produtos, pedidos e usuários com interface Streamlit.

## Documentação

Documentação do projeto em [doc/](doc/):

- [README_PRINCIPAL.md](doc/README_PRINCIPAL.md) - Documentação principal do sistema
- [CHANGELOG.md](doc/CHANGELOG.md) - Histórico de versões
- [COMO_OBTER_DATABASE_URL.md](doc/COMO_OBTER_DATABASE_URL.md) - Guia de DATABASE_URL
- [GUIA_LIMPEZA_BD.md](doc/GUIA_LIMPEZA_BD.md) - Limpeza e manutenção do banco
- [MIGRACAO_CONSINCO.md](doc/MIGRACAO_CONSINCO.md) - Guia de migração Consinco (legado)
- [README_MIGRATIONS.md](doc/README_MIGRATIONS.md) - Migrações de colunas (legado)

## Inicio rapido

```bash
pip install -r requirements.txt
streamlit run main.py
```

## Estrutura do projeto

```
ProjetoBak/
├── app.py                 # Aplicacao principal (funcionarios)
├── main.py                # Ponto de entrada e menu principal
├── page/                  # Paginas da aplicacao
├── scripts/               # Scripts auxiliares
├── tools/                 # Ferramentas de manutencao
├── doc/                   # Documentacao
├── bdados/                # Base de dados local
└── requirements.txt       # Dependencias Python
```

## Funcionalidades

### Funcionarios (Baklizi)
- Home
- Consulta de Mix
- Pedido de Consumo (para usuarios com lojas)
- Pedido por Codigo (CD) (para usuarios com lojas)
- Contato / chamados
- Alterar senha

### Administradores
- Aprovacao de pedidos
- Status do usuario (com cargo)
- Administracao de usuarios (roles user/admin, cargo, lojas)
- Admin Uploads

### Fornecedor/Promotor
- Pagina inicial do fornecedor
- Contato / suporte
- Admin de fornecedores (para role admin_fornecedor)

## Licenca

Projeto privado - Bakizi
