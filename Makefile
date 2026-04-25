.PHONY: dev-up dev-down customer-up customer-down logs logs-backend \
        status health ingest summary alerts use-csv use-json \
        psql reset-db build-images open help

DEV     = -f docker-compose.yml -f docker-compose.dev.yml
CUST    = -f docker-compose.yml -f docker-compose.customer.yml

# ── Developer lifecycle ───────────────────────────────────────────────────────
dev-up:       ## [DEV] Build and start all containers with hot reload
	@echo "🛠  Starting GBS Dashboard — DEVELOPER mode..."
	docker compose $(DEV) up --build -d
	@echo ""
	@echo "  Dashboard  →  http://localhost:3000"
	@echo "  API Docs   →  http://localhost:8000/docs"
	@echo "  API Health →  http://localhost:8000/health"

dev-down:     ## [DEV] Stop developer containers
	docker compose $(DEV) down

# ── Customer lifecycle ────────────────────────────────────────────────────────
customer-up:  ## [CUST] Start pre-built customer containers (images must be loaded first)
	@echo "🚀  Starting GBS Dashboard — CUSTOMER mode..."
	docker compose $(CUST) up -d
	@echo ""
	@echo "  Dashboard  →  http://localhost:3000"

customer-down: ## [CUST] Stop customer containers
	docker compose $(CUST) down

# ── Build and export images for customer delivery ─────────────────────────────
build-images: ## [CUST] Build and export images to .tar files for customer delivery
	@echo "📦  Building images..."
	docker build -t gbs-backend:1.0  ./backend
	docker build -t gbs-frontend:1.0 ./frontend
	docker save gbs-backend:1.0  -o gbs-backend.tar
	docker save gbs-frontend:1.0 -o gbs-frontend.tar
	@echo "✅  Images saved: gbs-backend.tar  gbs-frontend.tar"
	@echo "    Deliver these files + docker-compose.yml + docker-compose.customer.yml"
	@echo "    + infra/init.sql + data/aruba_health_7day.csv to the customer."

# ── Customer data volume setup ────────────────────────────────────────────────
customer-init-volume: ## [CUST] Create named volume and load 7-day CSV
	docker volume create gbs_data
	docker run --rm \
	  -v gbs_data:/data \
	  -v "$(shell pwd)/data":/src \
	  alpine cp /src/aruba_health_7day.csv /data/aruba_health.csv
	@echo "✅  Volume gbs_data created and loaded with aruba_health_7day.csv"

customer-update-csv: ## [CUST] Push a new CSV into the named volume and trigger ingest
	@test -n "$(CSV)" || (echo "Usage: make customer-update-csv CSV=path/to/file.csv" && exit 1)
	docker run --rm \
	  -v gbs_data:/data \
	  -v "$(shell pwd)":/src \
	  alpine cp /src/$(CSV) /data/aruba_health.csv
	curl -s -X POST http://localhost:8000/api/v1/wireless/ingest/trigger
	@echo "✅  CSV updated and ingest triggered"

# ── Shared operational commands ───────────────────────────────────────────────
logs:         ## Tail logs from all containers
	docker compose logs -f

logs-backend: ## Tail backend logs only
	docker compose logs -f backend

status:       ## Show container status
	docker compose ps

health:       ## Check backend health endpoint
	@curl -s http://localhost:8000/health | python3 -m json.tool

ingest:       ## Manually trigger an ingestion cycle
	@echo "⚡ Triggering ingestion cycle..."
	@curl -s -X POST http://localhost:8000/api/v1/wireless/ingest/trigger | python3 -m json.tool

summary:      ## Show current wireless summary JSON
	@curl -s http://localhost:8000/api/v1/wireless/summary | python3 -m json.tool

alerts:       ## Show active alerts JSON
	@curl -s http://localhost:8000/api/v1/wireless/alerts | python3 -m json.tool

psql:         ## Open psql shell in database container
	docker exec -it gbs_db psql -U gbs_user -d gbs_health

reset-db:     ## Drop and re-initialise database — DESTRUCTIVE
	@echo "⚠️  Deleting all stored metrics. Ctrl+C to cancel..."
	@sleep 3
	docker compose down -v
	docker compose $(DEV) up --build -d

open:         ## Open dashboard in browser
	open http://localhost:3000 2>/dev/null || xdg-open http://localhost:3000

help:         ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'
