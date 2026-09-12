# Kubera agent (Pipecat + Daily)

Conversational voice bot: **Sarvam realtime STT → OpenRouter LLM → Sarvam TTS** ([Pipecat example](https://github.com/pipecat-ai/pipecat/blob/main/examples/voice/voice-sarvam-realtime.py)).

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness |
| `POST` | `/sessions` | Create Daily room, start bot, return client token |
| `GET` | `/sessions/{id}` | Session status |
| `DELETE` | `/sessions/{id}` | End session (idempotent) |

## Setup

At the repo root, copy `.env.example` → `.env` and fill:

- `DAILY_API_KEY`
- `SARVAM_API_KEY` (STT + TTS)
- `OPENROUTER_API_KEY` (any OpenRouter model via `OPENROUTER_MODEL`)

```bash
uv sync
uv run uvicorn server:app --host 0.0.0.0 --port 7860 --reload
```
