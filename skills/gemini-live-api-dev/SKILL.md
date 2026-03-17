---
name: gemini-live-api-dev
description: Use esta skill ao construir aplicativos de streaming bidirecional em tempo real com a API Gemini Live. Cobre streaming de áudio/vídeo/texto baseado em WebSocket, detecção de atividade de voz (VAD), recursos de áudio nativos, chamada de função, gerenciamento de sessão, tokens efêmeros para autenticação do lado do cliente e todas as opções de configuração da Live API.
---

# Skill de Desenvolvimento da API Gemini Live

## Visão Geral
A API Live permite interações de voz e vídeo em tempo real com baixa latência com o Gemini através de WebSockets. 

### Principais Capacidades:
- **Streaming bidirecional de áudio** — Conversas em tempo real mic-para-alto-falante.
- **Streaming de vídeo** — Envio de quadros de câmera/tela junto com o áudio.
- **Entrada/saída de texto** — Envio e recebimento de texto em uma sessão ao vivo.
- **VAD (Detecção de Atividade de Voz)** — Tratamento automático de interrupções.
- **Áudio Nativo** — Diálogo afetivo, áudio proativo, pensamento.

## Modelos Recomendados
- `gemini-2.5-flash-native-audio-preview-12-2025`: Recomendado para todos os casos de uso da API Live. Janela de contexto de 128k.

## Formatos de Áudio
- **Entrada**: PCM bruto, little-endian, 16 bits, mono, 16kHz. Tipo MIME: `audio/pcm;rate=16000`
- **Saída**: PCM bruto, little-endian, 16 bits, mono, taxa de amostragem de 24kHz.

## Exemplo de Conexão (Python)
```python
from google.genai import types

config = types.LiveConnectConfig(
    response_modalities=[types.Modality.AUDIO],
    system_instruction=types.Content(
        parts=[types.Part(text="Você é um assistente prestativo.")]
    )
)

async with client.aio.live.connect(model="gemini-2.5-flash-native-audio-preview-12-2025", config=config) as session:
    await session.send_realtime_input(text="Olá, como você está?")
```

## Boas Práticas
1. Use fones de ouvido ao testar o áudio do microfone para evitar eco.
2. Ative a compressão da janela de contexto para sessões longas (>15 min).
3. Use tokens efêmeros para implementações no lado do cliente.
