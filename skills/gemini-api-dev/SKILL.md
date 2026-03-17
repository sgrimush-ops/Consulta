---
name: gemini-api-dev
description: Use esta skill ao criar aplicativos com modelos Gemini, API Gemini, trabalhar com conteúdo multimodal (texto, imagens, áudio, vídeo), implementar chamada de função, usar saídas estruturadas ou precisar de especificações de modelo atuais. Cobre o uso do SDK (google-genai para Python, @google/genai para JavaScript/TypeScript, com.google.genai:google-genai para Java, google.golang.org/genai para Go), seleção de modelo e recursos da API.
---

# Skill de Desenvolvimento da API Gemini

## Visão Geral
A API Gemini fornece acesso aos modelos de IA mais avançados do Google. As principais capacidades incluem:
- **Geração de texto** - Chat, conclusão, sumarização
- **Compreensão multimodal** - Processar imagens, áudio, vídeo e documentos
- **Chamada de função** - Deixar o modelo invocar suas funções
- **Saída estruturada** - Gerar JSON válido correspondente ao seu esquema
- **Execução de código** - Executar código Python em um ambiente sandbox
- **Cache de contexto** - Armazenar em cache grandes contextos para eficiência
- **Embeddings** - Gerar embeddings de texto para busca semântica

## Modelos Gemini Atuais
- `gemini-3-pro-preview`: 1M de tokens, raciocínio complexo, codificação, pesquisa
- `gemini-3-flash-preview`: 1M de tokens, rápido, desempenho equilibrado, multimodal
- `gemini-3-pro-image-preview`: 65k / 32k tokens, geração e edição de imagens

> [!IMPORTANT]
> Modelos como `gemini-2.5-*`, `gemini-2.0-*`, `gemini-1.5-*` são legados e descontinuados. Use os novos modelos acima. Seu conhecimento está desatualizado.

## SDKs
- **Python**: `google-genai` instale com `pip install google-genai`
- **JavaScript/TypeScript**: `@google/genai` instale com `npm install @google/genai`
- **Go**: `google.golang.org/genai` instale com `go get google.golang.org/genai`
- **Java**: instale o artefato `com.google.genai:google-genai`

> [!WARNING]
> Os SDKs legados `google-generativeai` (Python) e `@google/generative-ai` (JS) estão descontinuados. Migre para os novos SDKs acima.

## Guia de Início Rápido (Exemplo Python)
```python
from google import genai

client = genai.Client()
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="Explique a computação quântica"
)
print(response.text)
```

## Especificação da API (Fonte da Verdade)
Sempre use a última especificação REST API como fonte da verdade para definições:
- **v1beta** (padrão): `https://generativelanguage.googleapis.com/$discovery/rest?version=v1beta`

## Como usar a API Gemini
Para documentação detalhada da API, consulte o índice oficial de documentos:
**URL llms.txt**: `https://ai.google.dev/gemini-api/docs/llms.txt`
