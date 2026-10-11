.DEFAULT_GOAL := help
PY ?= python3

.PHONY: help install api web test lint typecheck build deploy

help: ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

install: ## Install backend (venv) and frontend dependencies
	cd backend && $(PY) -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
	cd frontend && npm install

api: ## Run the API locally on :8787 (no AWS account needed)
	cd backend && . .venv/bin/activate && PYTHONPATH=src ELOOP_MODE=local python -m eloop.devserver

web: ## Run the web app on :5173 (proxies /api to the local API)
	cd frontend && npm run dev

test: ## Backend tests (DynamoDB tests run against moto)
	cd backend && . .venv/bin/activate && pytest

lint: ## Lint the backend
	cd backend && . .venv/bin/activate && ruff check src tests

typecheck: ## Typecheck the frontend
	cd frontend && npm run typecheck

build: ## Build the frontend and the SAM application
	cd frontend && npm run build
	sam build --template-file infra/template.yaml

deploy: build ## Deploy the API stack (see README for first-time setup)
	sam deploy --template-file .aws-sam/build/template.yaml --config-file infra/samconfig.toml
