# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Butler is a serverless AI assistant bot using a **Router-Agent-Skill** architecture. It supports LINE Webhook (production) and FastAPI (local dev/frontend). LLM provider (Gemini or Claude) is switchable via environment variable.

## Repository Structure

```
ai-butler/
├── apps/
│   ├── api/          # Python 3.11 backend (all logic lives here)
│   │   ├── main.py       # LINE Webhook entry (Cloud Functions deployment)
│   │   ├── app.py        # FastAPI entry (local dev + frontend API)
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── config.py             # Model names & generation params
│   │       ├── agents/               # Intent parsing & flow control
│   │       ├── services/             # External adapters (Firestore, GCal, LLM)
│   │       │   └── llm/              # LLM abstraction layer
│   │       ├── skills/               # Atomic Python functions (deterministic)
│   │       ├── prompts/              # AI system prompt text files
│   │       ├── scripts/              # Standalone cron scripts (daily/weekly report)
│   │       └── utils/                # LINE Flex Message templates
│   └── web/          # Frontend (to be developed)
├── packages/         # Shared code across apps (types, utils, UI components)
├── docs/docs/        # Architecture decision records
└── .github/workflows/ # CI (flake8 + pytest), daily/weekly cron jobs
```

## Development Commands

### Backend

```bash
cd apps/api
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run local FastAPI server
uvicorn app:app --reload --port 8000

# Test the /chat endpoint
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "dev_user", "message": "明天下午三點開會"}' | python3 -m json.tool
```

Required `.env` in `apps/api/`:
```ini
CALENDAR_ID=...
GOOGLE_APPLICATION_CREDENTIALS=service_account.json
LLM_PROVIDER=gemini          # or claude
GOOGLE_GENAI_API_KEY=...     # always required (Embedding uses Gemini regardless)
# ANTHROPIC_API_KEY=...      # only if LLM_PROVIDER=claude
# CHANNEL_ACCESS_TOKEN / CHANNEL_SECRET  # only needed for main.py (LINE)
```

### Deploy to GCP Cloud Functions

```bash
gcloud functions deploy webhook \
  --gen2 --runtime=python311 --region=asia-east1 \
  --memory=512MiB --source=apps/api/ --entry-point=webhook \
  --trigger-http --allow-unauthenticated \
  --set-env-vars="LLM_PROVIDER=gemini,GOOGLE_GENAI_API_KEY=...,..."
```

## Architecture: Router-Agent-Skill Pattern

The 3-layer pattern keeps debugging clean:

- **Router** (`app.py` / `main.py`): Intent classification only. Calls `get_router_intent()` concurrently with embedding generation via `asyncio.gather`.
- **Agent** (`src/agents/`): Prompt management, parameter normalization (`_normalize_args`), flow control per domain (calendar / expense / chat).
- **Skill** (`src/skills/`): Pure deterministic Python — calls Google Calendar API or Google Sheets. AI never generates code here.

Key flows:
- Intent + Embedding are computed **concurrently** on every request (cold-start optimization).
- Memory workflow runs as a **background task** (`asyncio.create_task`) to avoid blocking the response.
- Embedding always uses `gemini-embedding-001` regardless of `LLM_PROVIDER` (vector space consistency).

## LLM Provider Switching

Change `LLM_PROVIDER` in `.env` — no code changes needed. Model names configured in `src/config.py`. The factory (`src/services/llm/factory.py`) instantiates the correct provider.

| `LLM_PROVIDER` | Router model | Agent model |
|---|---|---|
| `gemini` | `gemini-2.5-flash-lite` | `gemini-3-flash-preview` |
| `claude` | `claude-haiku-4-5` | `claude-sonnet-4-5` |

## Memory RAG System

Stored in GCP Firestore Native Vector Search (`memories` collection). Requires manual composite index setup:
- Field: `embedding` (Vector, dim: 768, COSINE)
- Field: `user_id` (Ascending)

Memory types: `technical_log`, `personal_fact`, `task_note`, `daily_log`.

## Two Entry Points

- `apps/api/main.py` — LINE Webhook handler for Cloud Functions. Depends on LINE SDK.
- `apps/api/app.py` — FastAPI server for local dev / future frontend. No LINE dependency. Both share the same core `handle_message` logic.

## CI/CD

- `.github/workflows/ci.yml` — flake8 lint + pytest on push
- `.github/workflows/daily_notify.yml` — 21:30 daily schedule report via LINE
- `.github/workflows/weekly_notify.yml` — Sunday 21:30 weekly schedule report
