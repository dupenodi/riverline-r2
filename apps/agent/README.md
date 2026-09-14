# Kubera agent (Pipecat + Daily)

Conversational voice bot: **Sarvam realtime STT → Sarvam LLM → Sarvam TTS**.

Collects simple incoming/outgoing money items via tools and stores them in SQLite.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness |
| `POST` | `/sessions` | Create Daily room, start bot, return client token |
| `GET` | `/sessions` | List past sessions (newest first) |
| `GET` | `/sessions/{id}` | Session status (live memory, else SQLite) |
| `GET` | `/sessions/{id}/transcript` | Settled turns for a session |
| `GET` | `/sessions/{id}/history` | Meta + transcript + transactions |
| `GET` | `/sessions/{id}/transactions` | Money items for a session |
| `DELETE` | `/sessions/{id}` | End session (idempotent) |

Sessions, transcripts, and transactions live in SQLite
(`apps/agent/data/kubera.db`, or `KUBERA_DB_PATH`).

## Setup

At the repo root, copy `.env.example` → `.env` and fill:

- `DAILY_API_KEY`
- `SARVAM_API_KEY` (STT + LLM + TTS)

```bash
uv sync
uv run uvicorn server:app --host 0.0.0.0 --port 7860 --reload
```
