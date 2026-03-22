# timelineviz — common dev tasks (see DEVELOPING.md for full guide)
UV ?= uv
PYTEST ?= pytest
PKG := timelineviz

.DEFAULT_GOAL := help

.PHONY: help install sync test test-html test-verbose test-no-cov build clean publish version cli-help example-charts

help:
	@echo "timelineviz — targets"
	@echo ""
	@echo "  make install         Editable install + dev deps: uv pip install -e \".[dev]\""
	@echo "  make sync            uv sync (lockfile / project env; dev deps if configured)"
	@echo "  make test            Run pytest with coverage (pyproject defaults)"
	@echo "  make test-html       Add HTML coverage report → htmlcov/index.html"
	@echo "  make test-verbose    pytest -v"
	@echo "  make test-no-cov     pytest without coverage (overrides addopts)"
	@echo "  make build           Build wheel/sdist (uv build → dist/)"
	@echo "  make clean           Remove dist, htmlcov, caches, coverage data, egg-info, __pycache__"
	@echo "  make publish         Publish to PyPI (uv publish)"
	@echo "  make version         Print package version"
	@echo "  make cli-help        timelineviz --help"
	@echo "  make example-charts  Regenerate docs images (examples/gen_charts.py)"
	@echo ""

install:
	$(UV) pip install -e ".[dev]"

sync:
	$(UV) sync --all-extras

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
	$(UV) build

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

example-charts:
	$(UV) run python examples/gen_charts.py
