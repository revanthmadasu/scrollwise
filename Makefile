# ScrollWise monorepo — root task runner.
# Each target delegates to a subproject. Run `make <target>`.

PY ?= python3
GEN_DIR := services/content-generator
API_DIR := apps/api
WEB_DIR := apps/web

.PHONY: help test test-generator test-api generate install-generator install-api install-web api web

help:
	@echo "ScrollWise monorepo targets:"
	@echo "  make install-generator  - install content-generator deps"
	@echo "  make install-api        - install API deps"
	@echo "  make test               - run all subproject tests"
	@echo "  make generate           - run the content generator (pass ARGS=...)"
	@echo "  make api                - run backend API (uvicorn, reload)"
	@echo "  make install-web        - install frontend deps (needs Node 18+)"
	@echo "  make web                - run frontend dev server (Vite, :5173)"

install-generator:
	cd $(GEN_DIR) && $(PY) -m pip install -r requirements.txt

install-api:
	cd $(API_DIR) && $(PY) -m pip install -r requirements.txt

# Aggregate test target. Add web suites here as they land.
test: test-generator test-api

test-generator:
	cd $(GEN_DIR) && $(PY) -m pytest tests/ -q

test-api:
	cd $(API_DIR) && $(PY) -m pytest -q

# Example: make generate ARGS='--topic "Stoicism" --modules 2 --subtopics-per-module 3'
generate:
	cd $(GEN_DIR) && $(PY) -m scripts.generate $(ARGS)

api:
	cd $(API_DIR) && $(PY) -m uvicorn app.main:app --reload

install-web:
	cd $(WEB_DIR) && npm install

web:
	cd $(WEB_DIR) && npm run dev
