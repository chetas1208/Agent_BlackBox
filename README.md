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
│  │ Service   │  │ Engine       │  │ (LLM + Demo Workers)   │  │
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
| Frontend | Nuxt 3, TypeScript, Tailwind CSS, VueUse |
| Backend | Python 3.12, FastAPI, Pydantic v2, OpenAI GPT-4o-mini |
| Storage | Redis 7 (sessions, memory, events, pub/sub) |
| Sandbox | Blaxel Cloud Sandbox (perpetual, stateful) |
| Auth | JWT + bcrypt, GitHub PAT integration |
| Infra | Docker Compose, Makefile |

## Features

- **Real LLM Agent** — GPT-4o-mini with tool-calling loop (clone repo, read/write files, run commands, create PRs)
- **Blaxel Sandbox** — Isolated cloud execution environment with full state preservation
- **Execution Sessions** — Create, start, pause, resume, and cancel agent tasks
- **Flight Recorder** — Every step logged as a typed event with severity, payload, and human-readable explanation
- **Layered Memory** — Working, episodic, semantic, and risk memory with confidence scoring
- **Safety Engine** — Retry loop, contradiction, drift, stall, and budget overrun detectors
- **Guardrails** — Pre-execution checks block dangerous commands (rm -rf, DROP TABLE, secret leaks)
- **Context Window Management** — Automatic compression of old conversation steps
- **Checkpointing** — Automatic and manual execution state snapshots
- **Recovery** — Restore to checkpoint, quarantine bad memory, replay execution
- **Agent Reports** — Auto-generated AGENT_REPORT.md with findings, rendered in UI
- **User Authentication** — Register, login, forgot/reset password with JWT
- **GitHub Integration** — Connect PAT to list repos from a dropdown
- **Real-time Streaming** — SSE event stream for live dashboard updates
- **Demo Scenarios** — 4 built-in scenarios: healthy, retry loop, contradiction, recovery
- **Docker Export** — Full application packaged as portable Docker images

---

## Quick Start

### Option 1: Docker (recommended — one command)

```bash
# 1. Clone the repo
git clone https://github.com/chetas1208/AI_Sandbox_Hack.git
cd AI_Sandbox_Hack

# 2. Configure environment
cp .env.example .env
# Edit .env with your OpenAI API key and Blaxel credentials

# 3. Build and run
make build
make up
```

Open http://localhost:3000 — that's it.

### Option 2: Import pre-built images (no build needed)

If someone shared the `agent-blackbox.tar.gz` file with you:

```bash
# 1. Load the images
make import
# or: docker load < agent-blackbox.tar.gz

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Run
make up
```

### Option 3: Local development (hot reload)

**Prerequisites:** Python 3.12+, Node.js 20+, Redis running on localhost:6379

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000 --env-file .env

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

---

## Docker Distribution

### Export (create portable package)

```bash
make export
```

This builds all images and saves them to **`agent-blackbox.tar.gz`** (~274 MB).

To run on any machine with Docker:

```
agent-blackbox.tar.gz    # All 3 Docker images (backend + frontend + Redis)
docker-compose.yml       # Orchestration
.env                     # Configuration (edit API keys)
Makefile                 # Convenience commands
```

### Import (on target machine)

```bash
make import    # loads images from agent-blackbox.tar.gz
make up        # starts all services
```

### Available Commands

```
make help       Show all commands
make build      Build Docker images
make up         Start all services (Redis + Backend + Frontend)
make down       Stop all services
make logs       Tail logs
make clean      Remove containers, volumes, images
make export     Save images to agent-blackbox.tar.gz
make import     Load images from agent-blackbox.tar.gz
```

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ABB_REDIS_URL` | Redis connection URL | `redis://redis:6379` (Docker) or `redis://localhost:6379` (local) |
| `ABB_OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `ABB_OPENAI_MODEL` | LLM model | `gpt-4o-mini` |
| `BL_WORKSPACE` | Blaxel workspace name | `myworkspace` |
| `BL_API_KEY` | Blaxel API key | `bl_...` |
| `ABB_SANDBOX_PROFILE` | Sandbox type | `blaxel` or `local_mock` |
| `ABB_DEBUG` | Debug mode | `true` / `false` |
| `ABB_CORS_ORIGINS` | Allowed CORS origins | `["http://localhost:3000"]` |

---

## How It Works

### New Developer Onboarding Use Case

1. **New developer joins** a company and needs to understand a repo
2. They **paste a GitHub repo URL** and describe their task ("set up CI pipeline", "fix failing tests")
3. Agent Black Box:
   - Spins up an isolated **Blaxel sandbox**
   - **Clones** the repo into the sandbox
   - GPT-4o-mini **analyzes** the codebase (reads files, runs tests, checks structure)
   - **Executes** the task (writes code, installs deps, runs commands)
   - **Generates a report** (AGENT_REPORT.md) summarizing findings
   - Optionally **creates a Pull Request** on GitHub
4. The entire process is **recorded** in the timeline with full observability
5. If anything goes wrong, the **Safety Engine** detects it and the **Recovery Engine** can roll back

### Demo Scenarios

| Scenario | Description | What Happens |
|----------|-------------|--------------|
| **Healthy** | Agent debugs a simple issue | Plans, reads code, runs tests, applies fix, verifies — completes clean |
| **Retry Loop** | Agent gets stuck retrying | Safety engine detects retry loop after 3 attempts, pauses execution |
| **Contradiction** | Agent relies on stale memory | New test run contradicts stored memory → quarantine + recovery |
| **Recovery** | Agent's refactor breaks tests | Fails → restores checkpoint → conservative fix → success |

---

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

### Checkpoints & Recovery
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sessions/{id}/checkpoints` | List checkpoints |
| POST | `/api/sessions/{id}/checkpoints` | Create checkpoint |
| POST | `/api/sessions/{id}/restore/{cp_id}` | Restore checkpoint |
| GET | `/api/sessions/{id}/recovery-report` | Get recovery report |

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Login (returns JWT) |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/auth/github-token` | Save GitHub PAT |
| GET | `/api/auth/github/repos` | List user's GitHub repos |
| POST | `/api/auth/forgot-password` | Request password reset |
| POST | `/api/auth/reset-password` | Reset password with token |

### Report
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sessions/{id}/report` | Get agent report (markdown) |

---

## Project Structure

```
AI_Sandbox_Hack/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI route handlers (sessions, auth, seed)
│   │   ├── core/         # Config, Redis connection
│   │   ├── models/       # Pydantic domain models
│   │   ├── schemas/      # Request/response schemas
│   │   ├── services/     # Business logic (auth, session, memory, etc.)
│   │   ├── repositories/ # Redis data access layer
│   │   ├── workers/      # Agent runtime (LLM + demo scenarios)
│   │   ├── sandbox/      # Sandbox adapters (Blaxel, local mock)
│   │   ├── safety/       # Safety engine & detectors
│   │   └── memory/       # Memory layer logic
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .dockerignore
├── frontend/
│   ├── components/       # Vue components (TimelineEvent, MemoryCard, etc.)
│   ├── composables/      # Vue composables (useApi, useAuth, useEventStream)
│   ├── layouts/          # App layout with auth-aware navbar
│   ├── pages/            # Nuxt pages (dashboard, session detail, login, etc.)
│   ├── types/            # TypeScript type definitions
│   ├── utils/            # Formatting utilities
│   ├── assets/css/       # Tailwind styles
│   ├── nuxt.config.ts
│   ├── Dockerfile
│   └── .dockerignore
├── docker-compose.yml    # Full stack orchestration
├── Makefile              # Build, run, export, import commands
├── .env.example          # Environment variable template
└── README.md
```

## License

MIT
