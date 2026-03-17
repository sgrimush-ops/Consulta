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

## Integracao de agentes, squads e skills

O projeto agora possui uma camada de integracao para uso no VS Code/Copilot, sem alterar o fluxo principal da aplicacao Streamlit.

- `.github/copilot-instructions.md`: contexto global do projeto para o agente.
- `.github/agents/`: agentes especializados para operacao de varejo, dados e engenharia.
- `.github/skills/`: skills reaproveitaveis para governanca e carga/sanitizacao de dados.
- `.github/prompts/executar-squad-varejo-insight.prompt.md`: atalho para rodar a orquestracao do squad Varejo Insight.
- `squads/varejo-insight/`: definicao canonica do squad, party, pipeline e artefatos de dominio.

Detalhes operacionais estao em `doc/AGENTES_SQUADS_SKILLS.md`.

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
- Integracao de IA para agentes, squads e skills

### Atualizações recentes
- Pedido por Codigo (CD) exige escolha de CD abastecedor (`CD15` ou `CD16`) antes de enviar
- Aprovacao exibe origem do pedido CD com o abastecedor (`CD15`/`CD16`)
- Download de aprovados considera ultimos 5 minutos e gera arquivo `pedido.xlsx`
- Exportacao consolida repeticoes do mesmo item por loja no mesmo dia

### Padrao de data/hora (Brasilia)
- Gravacoes de data/hora do sistema seguem `America/Sao_Paulo`
- Conexoes com Postgres configuram timezone de sessao para Brasilia
- Consultas de janela temporal (ex.: ultimos 30 dias) usam referencia BRT

### Fornecedor/Promotor
- Pagina inicial do fornecedor
- Contato / suporte
- Admin de fornecedores (para role admin_fornecedor)

## Licenca

Projeto privado - Bakizi
