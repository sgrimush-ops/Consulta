# ProjetoBak - Gestão de Produtos

Sistema completo de gestão de produtos, pedidos e ofertas com interface Streamlit.

## � Documentação

Toda a documentação do projeto está armazenada na pasta [`doc/`](./doc/):

- **[README_PRINCIPAL.md](./doc/README_PRINCIPAL.md)** - Documentação principal do projeto
- **[CHANGELOG.md](./doc/CHANGELOG.md)** - Histórico de atualizações e versões
- **[SOLUCAO_RAPIDA.md](./doc/SOLUCAO_RAPIDA.md)** - Soluções rápidas e troubleshooting
- **[COMO_OBTER_DATABASE_URL.md](./doc/COMO_OBTER_DATABASE_URL.md)** - Guia para configurar DATABASE_URL
- **[CORRECAO_OFERTAS.md](./doc/CORRECAO_OFERTAS.md)** - Documentação de correção de ofertas
- **[README_TOOLS.md](./doc/README_TOOLS.md)** - Documentação das ferramentas auxiliares
- **[README_MIGRATIONS.md](./doc/README_MIGRATIONS.md)** - Documentação de migrações de banco de dados

## 🚀 Início Rápido

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar a aplicação
streamlit run main.py
```

## 📁 Estrutura do Projeto

```
ProjetoBak/
├── app.py                 # Aplicação principal
├── main.py               # Ponto de entrada
├── page/                 # Páginas da aplicação
├── scripts/              # Scripts auxiliares
├── tools/                # Ferramentas de desenvolvimento
├── migrations/           # Migrações de banco de dados
├── doc/                  # Documentação completa
└── requirements.txt      # Dependências Python
```

## 🔧 Funcionalidades

### Para Usuários
- ✅ **Dashboard Online** - Visualização de métricas e análises
- ✅ **Consulta de Estoque e Mix (CD)** - Busca de produtos disponíveis
- ✅ **Pedido por Código (CD)** - Pedidos via código interno ou EAN
- ✅ **Pedidos de Promoção** - Gestão de pedidos promocionais
- ✅ **Ofertas Atuais** - Visualização de ofertas vigentes
- ✅ **Sistema de Contato** - Abertura e acompanhamento de chamados
- ✅ **Alterar Senha** - Gerenciamento de credenciais

### Para Administradores
- ✅ **Aprovação de Pedidos** - Validação e processamento de solicitações
- ✅ **Upload de Ofertas** - Importação em lote de ofertas (MKT/Admin)
- ✅ **Admin Uploads** - Gerenciamento de arquivos enviados
- ✅ **Status do Usuário** - Monitoramento de usuários online
- ✅ **Administração** - Criação e gestão de usuários
- ✅ **Dashboard** - Análises e métricas gerenciais

## 📝 Licença

Projeto privado - Bakizi
