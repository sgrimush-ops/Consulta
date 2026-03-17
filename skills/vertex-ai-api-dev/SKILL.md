---
name: vertex-ai-api-dev
description: Guia o uso da API Gemini no Google Cloud Vertex AI com o Gen AI SDK. Use quando o usuário perguntar sobre o uso do Gemini em um ambiente corporativo ou mencionar explicitamente o Vertex AI. Cobre o uso do SDK (Python, JS/TS, Go, Java, C#), recursos como Live API, ferramentas, geração multimodal, cache e predição em lote.
compatibility: Requer credenciais ativas do Google Cloud e API Vertex AI ativada.
---

# Gemini API no Vertex AI

Acesse os modelos de IA mais avançados do Google criados para casos de uso corporativos usando a API Gemini no Vertex AI.

## Diretrizes Principais
- **SDK Unificado**: SEMPRE use o Gen AI SDK (`google-genai` para Python, `@google/genai` para JS/TS, `google.golang.org/genai` para Go, `com.google.genai:google-genai` para Java, `Google.GenAI` para C#).
- **SDKs Legados**: NÃO use `google-cloud-aiplatform`, `@google-cloud/vertexai` ou `google-generativeai`.

## Autenticação e Configuração
Prefira variáveis de ambiente em vez de parâmetros fixos no código:
```bash
export GOOGLE_CLOUD_PROJECT='seu-project-id'
export GOOGLE_CLOUD_LOCATION='global'
export GOOGLE_GENAI_USE_VERTEXAI=true
```

## Inicialização (Python)
```python
from google import genai
client = genai.Client() # Pega automaticamente as variáveis de ambiente
```

## Modelos
- `gemini-3.1-pro-preview` (1M tokens): raciocínio complexo, codificação, pesquisa.
- `gemini-3-flash-preview` (1M tokens): rápido, desempenho equilibrado, multimodal.
- `gemini-live-2.5-flash-native-audio`: para Live Realtime API com áudio nativo.

## Documentação e APIs (Fonte da Verdade)
- **Documentação Vertex AI Gemini**: [cloud.google.com/vertex-ai/generative-ai/docs/](https://cloud.google.com/vertex-ai/generative-ai/docs/)
- **Referência da API REST**: [cloud.google.com/vertex-ai/generative-ai/docs/reference/rest](https://cloud.google.com/vertex-ai/generative-ai/docs/reference/rest)
