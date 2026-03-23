# Development Guide

Setup, testing, and release instructions for `timelineviz`.

## Makefile

The repository root includes a `Makefile` for routine tasks. It invokes **`uv`** by default; override with `make UV=path/to/uv` if needed. Run **`make`** or **`make help`** to print the same target list as below.

| Target | Description |
|--------|-------------|
| `install` | Editable install with dev dependencies (`uv pip install -e ".[dev]"`) |
| `sync` | `uv sync --all-extras` — project environment from `pyproject.toml` / `uv.lock` (includes optional extras such as `dev`) |
| `test` | `uv run pytest` with coverage (uses `[tool.pytest.ini_options]` in `pyproject.toml`) |
| `test-html` | Same as `test`, plus HTML coverage under `htmlcov/` |
| `test-verbose` | `pytest -v` |
| `test-no-cov` | Pytest without coverage (`-o addopts=`) |
| `build` | `uv build` → `dist/` |
| `clean` | Remove `dist`, `build`, `htmlcov`, pytest and coverage caches, `*.egg-info`, and `__pycache__` (skips `.venv` and `.git`) |
| `publish` | `uv publish` |
| `version` | Print `timelineviz.__version__` |
| `cli-help` | `timelineviz --help` |
| `example-charts` | Regenerate documentation images (`examples/gen_charts.py`) |

Override the test runner with `make PYTEST=pytest …` if required.

## Setup

```bash
git clone https://github.com/garrywilliams/timeline_viz.git
cd timeline_viz
make install
# or: uv pip install -e ".[dev]"

# Optional: uv-managed env and lockfile (see `uv sync` docs)
make sync
```

## Testing

```bash
make test
make test-html    # then open htmlcov/index.html
make test-no-cov  # faster iteration without coverage
```

Equivalently, with `uv` and the project on the path:

```bash
uv run pytest
uv run pytest --cov-report=html
open htmlcov/index.html   # macOS
```

Coverage threshold is 90 % (enforced in `pyproject.toml`).

## Project Layout

```
src/timelineviz/
    __init__.py       # Public API re-exports
    _version.py       # Single source of truth for version
    timeline.py       # CSV/DataFrame visualisation
    promtest.py       # Prometheus test file parser + visualiser
    utils.py          # Shared helpers
    cli.py            # CLI entry point (wide CSV, --event-log, --promtest)
    py.typed          # PEP 561 marker
    tests/
        test_timeline.py
        test_promtest.py
        test_utils.py
        test_cli.py
```

Long-format logs (one timestamp column across many rows, optional row filters) are handled by `plot_event_log_timeline` in `timeline.py` and by CLI flags `--event-log` and `--log-*` (see README).

## Building

```bash
make build
# or: uv build
# outputs dist/timelineviz-x.y.z-py3-none-any.whl (and sdist)
```

## Release Process

1. Bump version in `src/timelineviz/_version.py`
2. Update `CHANGELOG.md`
3. Commit, tag, push:
   ```bash
   git tag v0.1.0
   git push origin main --tags
   ```
4. Publish to PyPI:
   ```bash
   make publish
   # or: uv publish
   ```