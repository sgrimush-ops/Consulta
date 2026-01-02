# Histórico de Atualizações - ProjetoBak

## 📅 02/01/2026 - Versão 1.5.0

### ✨ Novas Funcionalidades

#### Scanner de Código de Barras 📱
- **Página:** Pedido por Código (CD)
- **Descrição:** Leitura automática de códigos EAN através da câmera do dispositivo
- **Tecnologia:** pyzbar + Streamlit camera_input
- **Formatos suportados:** EAN-13, EAN-8, UPC-A, UPC-E, Code 128, QR Code
- **Benefícios:**
  - Elimina erros de digitação
  - Agiliza processo de pedidos
  - Otimizado para dispositivos móveis
  - Mantém opção de digitação manual

### 📝 Arquivos Adicionados
- `scripts/test_barcode_scanner.py` - Script de teste e validação
- `doc/SCANNER_CODIGO_BARRAS.md` - Documentação técnica completa
- `doc/CHANGELOG.md` - Histórico de versões

### 🔧 Arquivos Modificados
- `requirements.txt` - Adicionado `pyzbar==0.1.9`
- `page/pedido_cd.py` - Implementação do scanner
- `README.md` - Atualização com novas funcionalidades
- `doc/README_PRINCIPAL.md` - Estrutura e funcionalidades atualizadas
- `doc/README_TOOLS.md` - Inclusão do script de teste

### 📦 Dependências Atualizadas
```diff
+ pyzbar==0.1.9
```

### 🗑️ Funcionalidades Descontinuadas
- **Área de Fornecedores** - Páginas existem mas não estão mais no menu:
  - `page/area_fornecedor.py` (não referenciado)
  - `page/admin_fornecedor.py` (não referenciado)
  - `page/contato_fornecedor.py` (não referenciado)
- **Digitar Pedidos (Legado)** - Removido junto com `pedidos.py`

### 🎯 Melhorias de Documentação
- ✅ Documentação principal atualizada com estrutura completa do projeto
- ✅ Lista de funcionalidades reorganizada por perfil de usuário
- ✅ Novo guia técnico do scanner com troubleshooting
- ✅ Remoção de referências a funcionalidades obsoletas

---

## Versões Anteriores

### Versão 1.4.x
- Sistema de contato e chamados
- Dashboard online
- Gestão de promoções
- Consulta de estoque e mix

### Versão 1.3.x
- Aprovação de pedidos
- Upload de ofertas
- Admin uploads

### Versão 1.2.x
- Migrações de banco de dados
- Scripts de limpeza automática
- Ferramentas de diagnóstico

### Versão 1.1.x
- Sistema base de pedidos
- Gerenciamento de usuários
- Autenticação e autorização

### Versão 1.0.x
- Versão inicial do sistema

---

**Mantido por:** Equipe Bakizi  
**Última atualização:** 02/01/2026
