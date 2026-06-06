# ScrollWise monorepo — root task runner.
# Each target delegates to a subproject. Run `make <target>`.

PY ?= python3
GEN_DIR := services/content-generator

.PHONY: help test test-generator generate install-generator api web

help:
	@echo "ScrollWise monorepo targets:"
	@echo "  make install-generator  - install content-generator deps"
	@echo "  make test               - run all subproject tests"
	@echo "  make generate           - run the content generator (pass ARGS=...)"
	@echo "  make api                - run backend API (not built yet)"
	@echo "  make web                - run frontend (not built yet)"

install-generator:
	cd $(GEN_DIR) && $(PY) -m pip install -r requirements.txt

# Aggregate test target. Add api/web suites here as they land.
test: test-generator

test-generator:
	cd $(GEN_DIR) && $(PY) -m pytest tests/ -q

# Example: make generate ARGS='--topic "Stoicism" --modules 2 --subtopics-per-module 3'
generate:
	cd $(GEN_DIR) && $(PY) -m scripts.generate $(ARGS)

api:
	@echo "apps/api not built yet."

web:
	@echo "apps/web not built yet."
