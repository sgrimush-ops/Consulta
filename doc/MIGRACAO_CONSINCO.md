# Migração para o Sistema Consinco - Guia de Referência Rápida

**Data:** 02/02/2026  
**Versão:** 2.0.0

---

## 📋 Resumo das Mudanças

### 1. Novo Sistema de Códigos

#### ANTES:
- Código antigo do sistema anterior
- Não especificado na estrutura

#### AGORA:
- **Código Principal:** `cod_consinco` (sistema Consinco)
- **Código Legado:** Disponível na coluna `transicao`
- **Arquivo:** `bdados/con5cod.parquet`

---

## 📊 Estrutura do Arquivo de Dados

### Arquivo: `bdados/con5cod.parquet`

| Coluna | Tipo | Descrição | Exemplo |
|--------|------|-----------|---------|
| `cod_consinco` | int64 | Código principal do produto no sistema Consinco | 10480 |
| `descricao` | string | Descrição atualizada do produto | "CERVEJA SKOL LATA 350ML" |
| `transicao` | int64 | Código do sistema anterior (para referência) | 1234 |
| `Mix` | string | Status: "A" = Ativo, "S" = Suspenso | "A" |
| `Emb` | int64 | Quantidade de unidades na embalagem | 12 |

### Estatísticas do Arquivo:
- **Total de produtos:** 36.063
- **Produtos ativos:** Filtrados por Mix = "A"
- **Produtos suspensos:** Mix = "S"

---

## 🆕 Nova Página: Consulta de Mix

### Localização
- **Arquivo:** `page/consulta_mix.py`
- **Menu:** "Consulta de Mix"
- **Acesso:** Todos os usuários logados

### Funcionalidades

#### 1. Busca por Código Consinco
- Digite o código numérico
- Resultado imediato do produto
- Indica se o produto está ativo ou suspenso
- Mostra código de transição (antigo)

#### 2. Busca por Descrição
- Digite qualquer parte da descrição (mínimo 3 caracteres)
- Busca case-insensitive
- Retorna todos os produtos que contenham o termo
- Filtros adicionais por embalagem

#### 3. Visualização Completa
- Opção para ver todos os produtos ativos
- Exportação para CSV
- Estatísticas do mix

### Informações Exibidas
- ✅ Código Consinco
- ✅ Descrição completa
- ✅ Código de Transição (antigo)
- ✅ Status (Ativo/Suspenso)
- ✅ Quantidade da Embalagem

---

## ❌ Páginas Removidas

As seguintes funcionalidades foram **descontinuadas** e suas páginas foram removidas:

### 1. Consulta de Estoque e Mix (CD)
- ❌ Arquivo: `page/consulta_cd.py`
- ✅ Substituída por: `page/consulta_mix.py`

### 2. Dashboard Online
- ❌ Arquivo: `page/dashboard_online.py`
- 📝 Motivo: Funcionalidade descontinuada

### 3. Sistema de Ofertas
- ❌ Upload de Ofertas: `page/upload_ofertas.py`
- ❌ Visualização de Ofertas: `page/ver_ofertas.py`
- 📝 Motivo: Sistema de ofertas descontinuado

### 4. Gestão de Promoções
- ❌ Arquivo: `page/gestao_promo.py`
- 📝 Motivo: Funcionalidade descontinuada

---

## 🔄 Menu Atualizado

### Menu Simplificado

#### Todos os Usuários:
```
📁 Home
🔍 Consulta de Mix (NOVO)
🔐 Alterar Senha
💬 Contato
```

#### Usuários com Acesso a Lojas:
```
+ 🛒 Pedido por Código (CD)
```

#### Administradores:
```
+ ✅ Aprovação de Pedidos
+ 👥 Status do Usuário
+ ⚙️ Administração
+ 📤 Admin Uploads
```

---

## 📝 Checklist de Migração

### Para Desenvolvedores:

- [x] Atualizar imports no `app.py`
- [x] Remover páginas obsoletas
- [x] Criar nova página de consulta de mix
- [x] Atualizar testes em `smoke_test.py`
- [x] Documentar mudanças no CHANGELOG

### Para Usuários:

- [ ] Familiarizar-se com a nova interface de consulta
- [ ] Mapear códigos antigos para `cod_consinco`
- [ ] Atualizar procedimentos que dependiam das páginas removidas
- [ ] Revisar fluxo de trabalho de pedidos

### Para Integrações:

- [ ] Atualizar APIs/scripts que usam códigos de produto
- [ ] Migrar de código antigo para `cod_consinco`
- [ ] Remover dependências do sistema de ofertas
- [ ] Verificar integrações com dashboard

---

## 🆘 Perguntas Frequentes

### 1. Como encontro o novo código de um produto antigo?
Use a busca por descrição na página "Consulta de Mix", ou consulte a coluna `transicao` no arquivo parquet.

### 2. O que aconteceu com o sistema de ofertas?
Foi descontinuado. A tabela ainda existe no banco de dados mas não é mais utilizada.

### 3. Como consulto produtos suspensos?
Na busca por código, o sistema informa se o produto está suspenso. Na busca por descrição, apenas produtos ativos são exibidos por padrão.

### 4. Posso exportar a lista de produtos?
Sim! A página de consulta oferece opção de download em CSV tanto para resultados de busca quanto para a lista completa.

### 5. Como faço pedidos agora?
O sistema de "Pedido por Código (CD)" permanece inalterado e deve usar os novos códigos Consinco.

---

## 📞 Suporte

Para dúvidas ou problemas:
1. Acesse a página "Contato" no menu
2. Abra um chamado descrevendo a questão
3. Aguarde retorno do suporte

---

**Documento gerado em:** 02/02/2026  
**Versão do Sistema:** 2.0.0  
**Responsável:** Equipe de Desenvolvimento
