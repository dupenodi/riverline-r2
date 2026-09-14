# Kubera — voice money agent

Monorepo for a conversational voice agent that collects incoming/outgoing money details:

| Path | Role |
|------|------|
| `apps/web` | Next.js frontend (Daily / Pipecat client) |
| `apps/agent` | Python voice agent (Pipecat + Daily) |

## Prerequisites

- Docker + Docker Compose, **or** Node 20+, Python 3.11+, [uv](https://docs.astral.sh/uv/)
- API keys: Daily, Sarvam

## Quick start (Docker)

```bash
cp .env.example .env
# fill DAILY_API_KEY, SARVAM_API_KEY
docker compose up --build
```

- Web: http://localhost:3000
- Agent health: http://localhost:7860/health

## Local development

**Agent**

```bash
cd apps/agent
# ensure repo-root .env has Daily + AI keys
uv sync
uv run uvicorn server:app --host 0.0.0.0 --port 7860 --reload
```

**Web**

```bash
cd apps/web
npm install
NEXT_PUBLIC_AGENT_URL=http://localhost:7860 npm run dev
```

## Session flow

1. Browser → `POST /sessions` (agent creates Daily room + starts bot)
2. Browser joins room with returned URL + token (Pipecat Daily transport)
3. Bot greets and converses (Sarvam STT → Sarvam LLM → Sarvam TTS)
4. Browser → `DELETE /sessions/{id}` to hang up

Diagram: [docs/user-flow.png](docs/user-flow.png).
