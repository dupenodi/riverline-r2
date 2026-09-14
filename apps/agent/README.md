# Kubera agent (Pipecat + Daily)

Conversational voice bot: **Sarvam realtime STT → Sarvam LLM → Sarvam TTS**
([realtime STT example](https://github.com/pipecat-ai/pipecat/blob/main/examples/voice/voice-sarvam-realtime.py),
[function-calling example](https://github.com/pipecat-ai/pipecat/blob/main/examples/function-calling/function-calling-sarvam.py)).

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness |
| `POST` | `/sessions` | Create Daily room, start bot, return client token |
| `GET` | `/sessions` | List past sessions (newest first) |
| `GET` | `/sessions/{id}` | Session status (live memory, else SQLite) |
| `GET` | `/sessions/{id}/transcript` | Settled turns for a session |
| `GET` | `/sessions/{id}/history` | Meta + transcript + latest finance |
| `GET` | `/sessions/{id}/finance` | Latest finance snapshot |
| `DELETE` | `/sessions/{id}` | End session (idempotent) |

Sessions, transcripts, and finance snapshots live in SQLite
(`apps/agent/data/kubera.db`, or `KUBERA_DB_PATH`).

## Setup

At the repo root, copy `.env.example` → `.env` and fill:

- `DAILY_API_KEY`
- `SARVAM_API_KEY` (STT + LLM + TTS)

```bash
uv sync
uv run uvicorn server:app --host 0.0.0.0 --port 7860 --reload
```
