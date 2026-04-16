.PHONY: help dev build up down logs clean export import

help:
	@echo ""
	@echo "  Agent Black Box — Commands"
	@echo "  ════════════════════════════════════════════"
	@echo ""
	@echo "  Development:"
	@echo "    make dev        Start locally (hot reload, no Docker)"
	@echo ""
	@echo "  Docker:"
	@echo "    make build      Build Docker images"
	@echo "    make up         Start all services (Redis + Backend + Frontend)"
	@echo "    make down       Stop all services"
	@echo "    make logs       Tail logs"
	@echo "    make clean      Remove containers, volumes, images"
	@echo ""
	@echo "  Distribution:"
	@echo "    make export     Save Docker images to agent-blackbox.tar.gz"
	@echo "    make import     Load Docker images from agent-blackbox.tar.gz"
	@echo ""

# Prefer Node 20+ on PATH (Homebrew: node@20). Avoids Nuxt CLI crash on Node 18 (util.styleText).
FRONTEND_NODE_PATH ?= /opt/homebrew/opt/node@20/bin:/usr/local/opt/node@20/bin

# ── Development (hot reload) ───────────────────────────────────
dev:
	@echo "Starting backend..."
	cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000 --env-file .env &
	@echo "Starting frontend (Node 20+ on PATH if installed via Homebrew)..."
	cd frontend && PATH="$(FRONTEND_NODE_PATH):$$PATH" npm run dev

# ── Docker Build ───────────────────────────────────────────────
build:
	@echo "🔨 Building Docker images..."
	docker compose build
	@echo ""
	@echo "✅ Images built:"
	@docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | grep -E "agent-blackbox|REPOSITORY"

# ── Start Everything ───────────────────────────────────────────
up:
	@test -f .env || (echo "❌ .env not found. Copy the example:" && echo "   cp .env.example .env" && exit 1)
	docker compose up -d
	@echo ""
	@echo "✅ Agent Black Box is running!"
	@echo ""
	@echo "   🌐 Frontend:  http://localhost:3000"
	@echo "   🔌 Backend:   http://localhost:8000"
	@echo "   📖 API docs:  http://localhost:8000/docs"
	@echo ""
	@echo "   Run 'make logs' to see output"
	@echo "   Run 'make down' to stop"

down:
	docker compose down

logs:
	docker compose logs -f

clean:
	docker compose down -v --rmi local
	docker system prune -f

# ── Export: save images to a portable tar.gz ───────────────────
export: build
	@echo "📦 Exporting Docker images to agent-blackbox.tar.gz ..."
	docker save agent-blackbox-backend:latest agent-blackbox-frontend:latest redis:7-alpine | gzip > agent-blackbox.tar.gz
	@echo ""
	@ls -lh agent-blackbox.tar.gz
	@echo ""
	@echo "✅ Export complete! Share these files to run anywhere:"
	@echo "   1. agent-blackbox.tar.gz  (Docker images)"
	@echo "   2. docker-compose.yml     (orchestration)"
	@echo "   3. .env                   (configuration)"
	@echo ""
	@echo "   On target machine:"
	@echo "     make import"
	@echo "     make up"

# ── Import: load images from tar.gz ───────────────────────────
import:
	@test -f agent-blackbox.tar.gz || (echo "❌ agent-blackbox.tar.gz not found" && exit 1)
	@echo "📥 Loading Docker images from agent-blackbox.tar.gz ..."
	docker load < agent-blackbox.tar.gz
	@echo ""
	@echo "✅ Images loaded. Run 'make up' to start."
