# Munim developer commands. Every target runs through uv so the locked environment is used.
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

UV ?= uv
PY := $(UV) run python
# Browsers for `make install` and `make e2e`. CI runs both; a machine that cannot
# download Firefox can run `make e2e E2E_BROWSERS="--browser chromium"`.
PW_BROWSERS ?= chromium firefox
E2E_BROWSERS ?= --browser chromium --browser firefox
PYTEST_FLAGS ?= -q --tb=short
CASE ?=

.PHONY: help install run check static design test test-fast e2e eval eval-repair fixtures \
        bless screens dossier-pdf ci tokens

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

install: ## Install Python 3.12 deps, git hooks and Playwright browsers
	$(UV) sync --all-packages --all-groups
	$(UV) run pre-commit install
	$(UV) run playwright install $(PW_BROWSERS)

run: ## Start the app on http://127.0.0.1:8765
	$(UV) run munim

tokens: ## Regenerate static/css/tokens.css from DESIGN.md
	$(PY) scripts/build_tokens.py

static: ## Lint, format check, types, import contracts, security, licences
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy packages/munim_core/src packages/munim_ai/src packages/munim_web/src packages/munim_mcp/src scripts
	$(UV) run lint-imports
	$(UV) run bandit -q -c pyproject.toml -r packages
	$(PY) scripts/check_licences.py
	$(PY) scripts/check_repo_files.py

design: ## Design lint, contrast, fonts, i18n, tokens up to date
	$(PY) scripts/build_tokens.py --check
	$(PY) scripts/design_lint.py
	$(PY) scripts/check_contrast.py
	$(PY) scripts/check_fonts.py
	$(PY) scripts/check_i18n.py

test-fast: ## Unit and property tests only
	$(UV) run pytest $(PYTEST_FLAGS) -m "unit or property"

test: ## Unit, property, integration, contract and golden tests with coverage gates
	$(UV) run pytest $(PYTEST_FLAGS) -m "not e2e and not a11y and not live" \
		--cov --cov-report=json:.coverage.json --cov-report=term:skip-covered
	$(PY) scripts/check_coverage.py .coverage.json

check: static design test ## Everything fast: static, design and tests (no browser)

e2e: ## Browser journeys and accessibility checks (Playwright, replay provider)
	$(UV) run pytest $(PYTEST_FLAGS) -m "e2e or a11y" $(E2E_BROWSERS)

fixtures: ## Regenerate the synthetic papers, ground truth and replay recordings
	$(PY) scripts/gen_fixtures.py

eval: ## Evaluation harness (MUNIM_PROVIDER, default replay) and report schema check
	$(PY) eval/run_eval.py
	$(PY) eval/validate_report.py eval/reports/latest.json

eval-repair: ## Repair-loop evaluation on injected single-character GSTIN faults
	$(PY) eval/run_eval.py --repair-only

bless: ## Re-bless golden files after reviewing the diff
	MUNIM_BLESS=1 $(UV) run pytest $(PYTEST_FLAGS) -m golden

screens: ## Screenshots of every page at 360/768/1440 in en and hi into docs/screens/
	$(PY) scripts/screens.py

dossier-pdf: ## Render a case's evidence file to PDF: make dossier-pdf CASE=<id>
	$(PY) scripts/dossier_pdf.py $(CASE)

ci: check e2e eval ## Everything except the live-model evaluation
