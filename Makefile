# timelineviz — common dev tasks (see DEVELOPING.md for full guide)
UV ?= uv
PYTEST ?= pytest
PKG := timelineviz
# Long-format / event-log smoke run (override for your own CSV)
EVENT_LOG_CSV ?= examples/incident_log.csv
EVENT_LOG_OUT ?= images

.DEFAULT_GOAL := help

.PHONY: help install sync lock lint format format-check test test-html test-verbose test-no-cov build dist-check check clean publish version cli-help precommit-install example-charts example-event-log

help:
	@echo "timelineviz — targets"
	@echo ""
	@echo "  make install         Sync editable project env with dev tools (uv sync --all-extras)"
	@echo "  make sync            Sync exactly to uv.lock (uv sync --locked --all-extras)"
	@echo "  make lock            Refresh uv.lock after dependency changes"
	@echo "  make lint            Ruff lint checks"
	@echo "  make format          Ruff formatter"
	@echo "  make format-check    Ruff formatter in check mode"
	@echo "  make test            Run pytest with coverage (pyproject defaults)"
	@echo "  make test-html       Add HTML coverage report → htmlcov/index.html"
	@echo "  make test-verbose    pytest -v"
	@echo "  make test-no-cov     pytest without coverage (overrides addopts)"
	@echo "  make build           Build wheel/sdist (uv build → dist/)"
	@echo "  make dist-check      Validate built artifacts with twine check"
	@echo "  make check           Local pre-PR gate: lint, format-check, tests, build, dist-check"
	@echo "  make clean           Remove dist, htmlcov, caches, coverage data, egg-info, __pycache__"
	@echo "  make publish         Manual PyPI publish fallback (prefer GitHub Release-driven publishing)"
	@echo "  make version         Print package version"
	@echo "  make cli-help        timelineviz --help"
	@echo "  make precommit-install  Install local git hooks"
	@echo "  make example-charts  Regenerate docs images (examples/gen_charts.py)"
	@echo "  make example-event-log  Smoke-test --event-log on EVENT_LOG_CSV → EVENT_LOG_OUT/event_log_timeline.png"
	@echo "                          (override: make example-event-log EVENT_LOG_CSV=foo.csv EVENT_LOG_OUT=out)"
	@echo ""

install:
	$(UV) sync --all-extras

sync:
	$(UV) sync --locked --all-extras

lock:
	$(UV) lock

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

format-check:
	$(UV) run ruff format --check .

test:
	$(UV) run $(PYTEST)

test-html:
	$(UV) run $(PYTEST) --cov-report=html
	@echo "Open htmlcov/index.html"

test-verbose:
	$(UV) run $(PYTEST) -v

test-no-cov:
	$(UV) run $(PYTEST) -o addopts=

build:
	rm -rf dist
	$(UV) build

dist-check:
	$(UV) run twine check --strict dist/*

check: lint format-check test build dist-check

clean:
	rm -rf dist build htmlcov .pytest_cache
	rm -f .coverage coverage.xml
	find . \( -path './.venv' -o -path './.git' \) -prune -o \
		-name '*.egg-info' -type d -exec rm -rf {} + 2>/dev/null || true
	find . \( -path './.venv' -o -path './.git' \) -prune -o \
		-type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

publish:
	$(UV) publish

version:
	@$(UV) run python -c "import $(PKG); print($(PKG).__version__)"

cli-help:
	@$(UV) run timelineviz --help

precommit-install:
	$(UV) run pre-commit install

example-charts:
	$(UV) run python examples/gen_charts.py

example-event-log:
	$(UV) run timelineviz $(EVENT_LOG_CSV) --event-log \
		--log-time-column ts \
		--log-label-column message \
		--log-filter-column level \
		--log-include ERROR WARN \
		--output-dir $(EVENT_LOG_OUT) \
		--no-show
	@echo "Wrote $(EVENT_LOG_OUT)/event_log_timeline.png"
