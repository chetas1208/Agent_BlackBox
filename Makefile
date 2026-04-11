.PHONY: help dev build up down logs clean

help:
	@echo "Agent Black Box — available commands:"
	@echo "  make dev      Start in development mode (hot reload)"
	@echo "  make build    Build Docker images"
	@echo "  make up       Start all services (production)"
	@echo "  make down     Stop all services"
	@echo "  make logs     Tail logs"
	@echo "  make clean    Remove containers and volumes"

# Development (hot reload, no Docker needed)
dev:
	@echo "Starting backend..."
	cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000 --env-file .env &
	@echo "Starting frontend..."
	cd frontend && npm run dev

# Docker builds
build:
	docker compose build

# Start everything via Docker
up:
	@test -f .env || (echo "ERROR: .env not found. Run: cp .env.example .env" && exit 1)
	docker compose up -d
	@echo ""
	@echo "✅ Agent Black Box is running:"
	@echo "   Frontend: http://localhost:3000"
	@echo "   Backend:  http://localhost:8000"
	@echo "   API docs: http://localhost:8000/docs"

# Start with local Redis (no Redis Cloud needed)
up-local:
	@test -f .env || (echo "ERROR: .env not found. Run: cp .env.example .env" && exit 1)
	docker compose --profile local-redis up -d

down:
	docker compose down

logs:
	docker compose logs -f

clean:
	docker compose down -v
	docker system prune -f
