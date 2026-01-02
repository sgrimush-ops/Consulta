# Como Habilitar o Scanner de Código de Barras no Render

## 🎯 Problema

O scanner de código de barras requer a biblioteca nativa `libzbar`, que não vem instalada por padrão no Render.

## ✅ Solução

### Opção 1: Usar apt-packages (Recomendado)

Crie um arquivo `apt-packages` na raiz do projeto:

```bash
# Arquivo: apt-packages
libzbar0
```

O Render instalará automaticamente durante o deploy.

### Opção 2: Script de Build Personalizado

No painel do Render, configure o **Build Command**:

```bash
apt-get update && apt-get install -y libzbar0 && pip install -r requirements.txt
```

### Opção 3: Dockerfile (Mais Controle)

Crie um `Dockerfile`:

```dockerfile
FROM python:3.12-slim

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    libzbar0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["streamlit", "run", "main.py", "--server.port=10000", "--server.address=0.0.0.0"]
```

## 📋 Verificação

Após o deploy, faça login como **admin** e acesse "Pedido por Código (CD)":

- ✅ **Scanner disponível**: Mensagem verde "Scanner de código de barras: Disponível"
- ❌ **Scanner indisponível**: Mensagem amarela com aviso

## 🔍 Troubleshooting

### Scanner não aparece mesmo após instalação

1. **Verifique os logs do build**:
   - Procure por erros na instalação do `libzbar0`
   - Confirme que `pyzbar` foi instalado

2. **Teste localmente**:
   ```bash
   python scripts/test_barcode_scanner.py
   ```

3. **Limpe o cache do Render**:
   - No painel do Render, force um novo deploy
   - Ou adicione uma variável de ambiente temporária para forçar rebuild

### Erro: "Unable to find zbar shared library"

A biblioteca `libzbar0` não foi instalada corretamente. Tente:

1. Verificar se o arquivo `apt-packages` está na raiz
2. Usar build command customizado
3. Migrar para Dockerfile

## 🌐 Alternativas se Render não Suportar

Se o Render não permitir instalação de bibliotecas nativas:

### 1. Usar Serviço de API Externa

- ZXing API: https://zxing.org/w/decode
- Barcode Lookup API
- Google Cloud Vision API

### 2. Migrar para Outro Host

Plataformas com melhor suporte a bibliotecas nativas:
- **Heroku** (com buildpacks)
- **Railway** (suporte nativo a apt)
- **DigitalOcean App Platform**
- **AWS Elastic Beanstalk**
- **Google Cloud Run** (com Dockerfile)

### 3. Manter Scanner Desabilitado

A aplicação funciona perfeitamente sem o scanner:
- Usuários digitam códigos manualmente
- Funcionalidade completa mantida
- Zero impacto na performance

## 📱 Importante

O scanner **sempre funcionará** em:
- ✅ Desenvolvimento local (se libzbar instalado)
- ✅ Dispositivos com a biblioteca instalada
- ✅ Ambientes Docker configurados

E **sempre terá fallback** para digitação manual em qualquer situação! 🎯

---

**Última atualização:** 02/01/2026
