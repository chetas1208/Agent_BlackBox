# Agent Black Box

**Runtime safety, observability, and recovery for autonomous AI agents.**

Agent Black Box is a flight recorder for long-running AI agents. It records what the agent was trying to do, tracks memory reads/writes, monitors tool calls, detects failures and drift, checkpoints execution state, and can rewind to safe checkpoints when things go wrong.

Think of it as **Datadog + Sentry for autonomous agents**, with runtime safety controls built in.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend (Nuxt 3)                     │
│  Dashboard │ Session Detail │ Memory Inspector │ Recovery UI │
└─────────────────────────────┬────────────────────────────────┘
                              │ REST + SSE
┌─────────────────────────────┴────────────────────────────────┐
│                       Backend (FastAPI)                       │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Session   │  │ Event        │  │ Safety Engine          │  │
│  │ Service   │  │ Recorder     │  │ - Retry loop detector  │  │
│  └──────────┘  └──────────────┘  │ - Contradiction det.   │  │
│  ┌──────────┐  ┌──────────────┐  │ - Drift detector       │  │
│  │ Memory   │  │ Checkpoint   │  │ - Budget overrun det.  │  │
│  │ Service   │  │ Service      │  │ - Stall detector       │  │
│  └──────────┘  └──────────────┘  └───────────────────────┘  │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Sandbox  │  │ Recovery     │  │ Agent Runtime          │  │
│  │ Service   │  │ Engine       │  │ (Background Workers)   │  │
│  └──────────┘  └──────────────┘  └───────────────────────┘  │
└─────────────────────────────┬────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │   Redis 7          │
                    │  - Sessions        │
                    │  - Events          │
                    │  - Memory layers   │
                    │  - Checkpoints     │
                    │  - Pub/Sub streams │
                    └───────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Nuxt 3, TypeScript, Tailwind CSS, Pinia, VueUse |
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| Storage | Redis 7 (sessions, memory, events, pub/sub) |
| Sandbox | Pluggable adapter (local mock included) |
| Infra | Docker Compose |

## Features

- **Execution Sessions** — Create, start, pause, resume, and cancel agent tasks
- **Flight Recorder** — Every step logged as a typed event with severity and metadata
- **Layered Memory** — Working, episodic, semantic, and risk memory with confidence scoring
- **Safety Engine** — Retry loop, contradiction, drift, stall, and budget overrun detectors
- **Checkpointing** — Automatic and manual execution state snapshots
- **Recovery** — Restore to checkpoint, quarantine bad memory, replay execution
- **Hybrid Execution Modes** — Demo mode for the built-in simulator, real mode for Codex + Blaxel orchestration
- **Sandbox Abstraction** — Pluggable execution environment with `local_mock` and `blaxel` adapters
- **Artifacts** — Structured run outputs for summaries, diffs, command logs, and file previews
- **Real-time Streaming** — SSE event stream for live dashboard updates
- **Demo Scenarios** — 4 built-in scenarios: healthy, retry loop, contradiction, recovery

## Execution Modes

### Demo mode

- Uses the existing simulated `AgentRuntime`
- Works with only Redis configured
- Ideal for local UI and safety-engine development

### Real mode

- Uses `RealExecutionOrchestrator`
- Requires `ABB_REAL_EXECUTION_ENABLED=true`
- Requires server-side `ABB_OPENAI_API_KEY`, `ABB_BLAXEL_API_KEY`, and `ABB_BL_WORKSPACE`
- Requires a Git `repo_url` and optional `repo_ref`
- Enforces repo-host and command guardrails before any sandbox execution

## Quick Start

### Option 1: Docker Compose (recommended)

```bash
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs

### Option 2: Local development

**Prerequisites:**
- Python 3.11+ for real mode
- Python 3.9+ is sufficient for demo mode
- Node.js 18+
- Redis running on localhost:6379

**Backend:**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate    # macOS/Linux
# venv\Scripts\activate     # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

## Real Mode Setup

Real mode is feature-flagged and intentionally fails fast when the provider stack is not configured.

Required backend env vars:

```bash
ABB_REAL_EXECUTION_ENABLED=true
ABB_REDIS_URL=redis://localhost:6379
ABB_ALLOWED_REPO_HOSTS=["github.com"]
ABB_OPENAI_API_KEY=...
ABB_OPENAI_MODEL_PLANNER=gpt-5-mini
ABB_OPENAI_MODEL_SUMMARY=gpt-5-nano
ABB_BLAXEL_API_KEY=...
ABB_BL_WORKSPACE=...
ABB_BLAXEL_REGION=us-pdx-1
ABB_BLAXEL_IMAGE=blaxel/base-image:latest
ABB_BLAXEL_SANDBOX_TTL=3600
ABB_TASK_MAX_STEPS=5
ABB_COMMAND_TIMEOUT_MS=60000
```

Notes:

- Keep provider secrets server-side only. Never expose them to Nuxt runtime config.
- The credentials pasted into chat should be rotated before production use.
- Real mode currently supports HTTPS Git repos only, with optional token injection through `ABB_GIT_ACCESS_TOKEN`.
- If config is incomplete, `POST /api/sessions` with `execution_mode="real"` returns a clear `400` instead of silently falling back to demo behavior.

### Seed Demo Data

Click the **"Seed Demo"** button in the UI, or call:

```bash
# Seed all 4 scenarios
curl -X POST http://localhost:8000/api/seed

# Seed a single scenario
curl -X POST http://localhost:8000/api/seed/healthy
curl -X POST http://localhost:8000/api/seed/retry_loop
curl -X POST http://localhost:8000/api/seed/contradiction
curl -X POST http://localhost:8000/api/seed/recovery
```

## Demo Scenarios

| Scenario | Description | What Happens |
|----------|-------------|--------------|
| **Healthy** | Agent debugs a simple issue | Plans, reads code, runs tests, applies fix, verifies — completes clean |
| **Retry Loop** | Agent gets stuck retrying a failing command | Safety engine detects retry loop after 3 attempts, pauses execution |
| **Contradiction** | Agent relies on stale cached memory | New test run contradicts stored "tests passing" memory → quarantine + recovery |
| **Recovery** | Agent's aggressive refactor breaks tests | Fails → restores checkpoint → conservative fix → success |

## API Reference

### Sessions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sessions` | Create session |
| GET | `/api/sessions` | List sessions |
| GET | `/api/sessions/{id}` | Get session |
| POST | `/api/sessions/{id}/start?scenario=healthy` | Start execution |
| POST | `/api/sessions/{id}/pause` | Pause |
| POST | `/api/sessions/{id}/resume` | Resume |
| POST | `/api/sessions/{id}/cancel` | Cancel |
| GET | `/api/sessions/{id}/artifacts` | List structured run artifacts |

### Events
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sessions/{id}/events` | Get all events |
| GET | `/api/sessions/{id}/events/stream` | SSE live stream |

### Memory
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sessions/{id}/memory` | List memory items |
| POST | `/api/sessions/{id}/memory` | Create memory |
| POST | `/api/memory/{id}/quarantine` | Quarantine memory |
| POST | `/api/memory/{id}/promote` | Promote memory |

### Checkpoints & Recovery
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sessions/{id}/checkpoints` | List checkpoints |
| POST | `/api/sessions/{id}/checkpoints` | Create checkpoint |
| POST | `/api/sessions/{id}/restore/{cp_id}` | Restore checkpoint |
| POST | `/api/sessions/{id}/replay` | Replay from last clean |
| GET | `/api/sessions/{id}/recovery-report` | Get recovery report |

## Project Structure

```
agent-black-box/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI route handlers
│   │   ├── core/         # Config, Redis connection
│   │   ├── models/       # Pydantic domain models
│   │   ├── schemas/      # Request/response schemas
│   │   ├── services/     # Business logic services
│   │   ├── repositories/ # Redis data access
│   │   ├── workers/      # Agent runtime & background jobs
│   │   ├── sandbox/      # Sandbox adapter abstraction
│   │   ├── safety/       # Safety engine & detectors
│   │   ├── memory/       # Memory layer logic
│   │   └── tests/        # Unit tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── components/       # Reusable Vue components
│   ├── composables/      # Vue composables (useApi, useEventStream)
│   ├── layouts/          # App layout
│   ├── pages/            # Nuxt pages (dashboard, session detail, new)
│   ├── types/            # TypeScript type definitions
│   ├── utils/            # Formatting utilities
│   ├── assets/css/       # Tailwind styles
│   ├── nuxt.config.ts
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## Extending the System

### Extending the real orchestration flow

- `backend/app/providers/codex_provider.py` owns structured planning, action selection, reflection, and summarization
- `backend/app/sandbox/blaxel_adapter.py` isolates Blaxel SDK details behind the existing sandbox interface
- `backend/app/services/real_execution_orchestrator.py` owns the request lifecycle for repo bootstrap, guarded execution, checkpoints, artifacts, and finalization
- `backend/app/services/redis_ops_service.py` owns ephemeral Redis state such as locks, rate limits, idempotency, run state, and plan caching

### Adding new safety detectors

Add a new method to `SafetyEngineService` in `backend/app/safety/engine.py`:

```python
async def detect_cost_spike(self, events, session) -> SafetyAlert | None:
    # Your detection logic
    ...
```

Then add it to `run_all_detectors()`.

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest app/tests/ -v
```

Current smoke coverage:

- backend imports cleanly with the new real-mode services
- Nuxt production build succeeds
- demo-mode session create/start/complete works in a live FastAPI process
- real-mode session creation fails cleanly when required provider config is missing

## License

MIT
