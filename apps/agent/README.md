# Riverline agent (Pipecat + Daily)

Session API scaffold:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness |
| `POST` | `/sessions` | Start session (placeholder Daily creds) |
| `GET` | `/sessions/{id}` | Session status |
| `DELETE` | `/sessions/{id}` | End session (idempotent) |

```bash
uv sync
uv run uvicorn server:app --host 0.0.0.0 --port 7860 --reload
```

Wire real Daily in `daily.py` and the Pipecat pipeline in `bot.py`.
