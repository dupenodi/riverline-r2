# Riverline AI Engineer take-home

Monorepo scaffold for a voice agent app:

| Path | Role |
|------|------|
| `apps/web` | Next.js frontend (Daily / Pipecat client) |
| `apps/agent` | Python voice agent (Pipecat + Daily) |

Agent conversation logic is intentionally not implemented yet — only structure, dependencies, and entry points.

## Prerequisites

- Docker + Docker Compose
- (Local dev) Node 20+, Python 3.11+, [uv](https://docs.astral.sh/uv/)

## Quick start (Docker)

```bash
cp .env.example .env
# add DAILY_API_KEY when you wire rooms
docker compose up --build
```

- Web: http://localhost:3000
- Agent health: http://localhost:7860/health

## Local development

**Agent**

```bash
cd apps/agent
cp ../../.env.example ../../.env   # once, at repo root
uv sync
uv run uvicorn server:app --host 0.0.0.0 --port 7860 --reload
```

**Web**

```bash
cd apps/web
npm install
NEXT_PUBLIC_AGENT_URL=http://localhost:7860 npm run dev
```

## Layout

```
apps/
  web/          Next.js App Router + Pipecat Daily transport
  agent/        FastAPI server + Pipecat bot stub
docs/
  user-flow.png Session connect/end sequence diagram
docker-compose.yml
.env.example
```

Session flow diagram: [docs/user-flow.png](docs/user-flow.png) (source: [docs/user-flow.mmd](docs/user-flow.mmd)).

## Session API (agent)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness |
| `POST` | `/sessions` | Start session |
| `GET` | `/sessions/{id}` | Status |
| `DELETE` | `/sessions/{id}` | End session |

Flow diagram: [docs/user-flow.png](docs/user-flow.png).

## Next steps

1. Real Daily room/token calls in `apps/agent/daily.py`
2. Pipecat pipeline in `apps/agent/bot.py`
3. `PipecatClient.connect` in `apps/web/src/components/VoiceCall.tsx`
