# Development Guide

Setup, testing, and release instructions for `timelineviz`.

## Setup

```bash
git clone https://github.com/garrywilliams/timeline_viz.git
cd timeline_viz
uv pip install -e ".[dev]"
```

## Testing

```bash
# Run tests with coverage
pytest

# HTML coverage report
pytest --cov=timelineviz --cov-report=html
open htmlcov/index.html
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
    cli.py            # CLI entry point
    py.typed          # PEP 561 marker
    tests/
        test_timeline.py
        test_promtest.py
        test_utils.py
        test_cli.py
```

## Building

```bash
uv build
# outputs dist/timelineviz-x.y.z-py3-none-any.whl
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
   uv publish
   ```