# Kubera agent

Sarvam realtime STT → Sarvam LLM → Sarvam TTS on Pipecat + Daily.

Setup, env vars, and `docker compose` live in the [repo README](../../README.md).

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness |
| `POST` | `/sessions` | Create Daily room, start bot, return client token |
| `GET` | `/sessions` | Past sessions (newest first) |
| `GET` | `/sessions/{id}` | Live memory, else SQLite |
| `GET` | `/sessions/{id}/transcript` | Settled turns |
| `GET` | `/sessions/{id}/history` | Meta + transcript + board |
| `GET` | `/sessions/{id}/transactions` | Money items |
| `DELETE` | `/sessions/{id}` | End session (idempotent) |

SQLite: `apps/agent/data/kubera.db`, or `KUBERA_DB_PATH`.

```bash
uv sync --dev
uv run uvicorn server:app --host 0.0.0.0 --port 7860 --reload
uv run pytest
```
