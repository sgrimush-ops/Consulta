# 🔧 Como Obter a DATABASE_URL

Para executar o script de correção, você precisa da string de conexão do banco de dados PostgreSQL.

## 📍 Onde Encontrar a DATABASE_URL

### Se estiver usando Render.com:
1. Acesse https://dashboard.render.com
2. Selecione seu serviço de banco de dados PostgreSQL
3. Vá em **"Info"** ou **"Connect"**
4. Copie a **"External Database URL"**

### Se estiver usando Heroku:
1. Acesse https://dashboard.heroku.com
2. Selecione sua aplicação
3. Vá em **Settings** → **Config Vars**
4. Copie o valor de `DATABASE_URL`

### Se estiver usando outro provedor:
Procure por "Connection String" ou "Database URL" no painel de controle.

---

## ⚡ Como Usar a DATABASE_URL

### Opção 1: Definir temporariamente no terminal

```bash
export DATABASE_URL='postgresql://usuario:senha@host:porta/banco'
python3 diagnose_ofertas.py
```

**Exemplo real:**
```bash
export DATABASE_URL='postgresql://baklizi_user:abc123@dpg-xyz.oregon-postgres.render.com:5432/baklizi_db'
python3 diagnose_ofertas.py
```

### Opção 2: Criar arquivo .env (Recomendado para desenvolvimento)

```bash
# Crie o arquivo .env
cat > .env << 'EOF'
DATABASE_URL=postgresql://usuario:senha@host:porta/banco
EOF

# Carregue as variáveis
export $(cat .env | xargs)

# Execute o script
python3 diagnose_ofertas.py
```

### Opção 3: Usar o script interativo

```bash
python3 find_and_fix_db.py
```

Este script irá:
- ✓ Procurar DATABASE_URL automaticamente
- ✓ Solicitar que você forneça se não encontrar
- ✓ Executar a correção automaticamente

---

## 🔒 Segurança

**⚠️ IMPORTANTE:**
- Nunca commite a `DATABASE_URL` no Git!
- O arquivo `.env` deve estar no `.gitignore`
- Use variáveis de ambiente em produção

---

## 📝 Formato da DATABASE_URL

```
postgresql://[usuario]:[senha]@[host]:[porta]/[nome_banco]
```

**Componentes:**
- `usuario`: Nome do usuário do banco (ex: postgres, baklizi_user)
- `senha`: Senha do banco (pode conter caracteres especiais)
- `host`: Endereço do servidor (ex: localhost, dpg-xyz.oregon-postgres.render.com)
- `porta`: Porta do PostgreSQL (geralmente 5432)
- `nome_banco`: Nome do banco de dados (ex: baklizi_db)

**Exemplo completo:**
```
postgresql://postgres:minha_senha_123@localhost:5432/baklizi
```

---

## 🐛 Problemas Comuns

### Erro: "password authentication failed"
- Verifique se usuário e senha estão corretos
- Caracteres especiais na senha devem ser URL-encoded

### Erro: "could not connect to server"
- Verifique se o host e porta estão corretos
- Certifique-se de que o firewall permite a conexão

### Erro: "SSL connection required"
- Adicione `?sslmode=require` no final da URL:
  ```
  postgresql://user:pass@host:5432/db?sslmode=require
  ```

---

## ✅ Próximos Passos

Depois de obter a DATABASE_URL:

1. **Execute o diagnóstico:**
   ```bash
   export DATABASE_URL='sua_url_aqui'
   python3 diagnose_ofertas.py
   ```

2. **Ou use o script interativo:**
   ```bash
   python3 find_and_fix_db.py
   ```

3. **Verifique os resultados** e confirme que a migração foi aplicada

---

## 📞 Ainda com Problemas?

Se não conseguir encontrar a DATABASE_URL:
1. Verifique com a pessoa que configurou o banco de dados
2. Procure em arquivos de configuração do deploy (Render, Heroku, etc.)
3. Verifique se há um arquivo `secrets.toml` ou similar no projeto
