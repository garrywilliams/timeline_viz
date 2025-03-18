# Development Guide

This guide covers development setup, testing, and contribution guidelines for Timeline Viz.

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/timeline_viz.git
cd timeline_viz
```

2. Install development dependencies:
```bash
# Using uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv pip install -e ".[test]"

# Or using pip
pip install -e ".[test]"
```

## Testing

Run the tests:
```bash
# Run basic tests
pytest

# Run with coverage
pytest --cov=timeline_viz

# Generate HTML coverage report
pytest --cov=timeline_viz --cov-report=html

# Run with minimum coverage enforcement
pytest --cov=timeline_viz --cov-fail-under=90
```

The HTML coverage report will be available in the `htmlcov` directory.

## Code Quality

### Pre-commit Hooks

We use pre-commit hooks to maintain code quality:

1. Install pre-commit:
```bash
uv pip install pre-commit
```

2. Install the hooks:
```bash
pre-commit install
```

The pre-commit configuration (`.pre-commit-config.yaml`):
```yaml
repos:
-   repo: local
    hooks:
    -   id: pytest
        name: pytest
        entry: pytest
        language: system
        types: [python]
        pass_filenames: false
```

## Dependencies

### Runtime Dependencies
- Python 3.6+
- NumPy
- Pandas
- Matplotlib

### Development Dependencies
- pytest
- pytest-cov
- pre-commit

These are specified in `pyproject.toml`:
```toml
[project.optional-dependencies]
test = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]
```

## Building

To build the package:
```bash
# Using uv (recommended)
uv build

# Install the built wheel
pipx install dist/*.whl
```

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create and push a tag
4. Build and upload to PyPI