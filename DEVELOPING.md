# Development Workflow for timeline_viz with uv

This guide explains how to set up and use the timeline_viz library in a development environment using uv.

## Structure
```
your_project/
├── .venv/                  # Your virtual environment 
├── notebooks/              # Your Jupyter notebooks
│   └── timeline_examples.ipynb
├── timeline_viz/           # The timeline visualization library
│   ├── __init__.py
│   ├── timeline.py
│   ├── cli.py
│   ├── utils.py
│   └── pyproject.toml
├── data/                   # Your data files
│   └── events.csv
└── pyproject.toml          # Main project config
```

## Setup Steps

1. **Install timeline_viz in development mode**

   From your project root directory (where your `.venv` is):

   ```bash
   # Activate your virtual environment if not already active
   source .venv/bin/activate  # On Linux/Mac
   # or
   .venv\Scripts\activate     # On Windows
   
   # Install timeline_viz in development mode with uv
   uv pip install -e ./timeline_viz
   ```

   The `-e` flag installs the package in "editable" mode, meaning changes to the source code will be immediately available without reinstalling.

2. **Verify installation**

   ```bash
   # Check that timeline_viz is installed
   uv pip list | grep timeline_viz
   
   # Test the CLI tool
   timeline-viz --help
   ```

3. **Using in notebooks**

   In your Jupyter notebooks, you can now import and use timeline_viz:

   ```python
   from timeline_viz import plot_timeline, plot_multiple_timelines
   
   # Your visualization code here...
   ```

## Development Workflow

When developing and making changes to the timeline_viz library:

1. Make changes to the source files in `timeline_viz/`
2. No need to reinstall - changes are immediately available due to the editable installation
3. Refresh or restart your Jupyter kernel if necessary to pick up changes

## Updating Dependencies

If you need to add or update dependencies:

1. Edit the `pyproject.toml` file in the `timeline_viz` directory
2. Update your installation:

   ```bash
   uv pip install -e ./timeline_viz
   ```

## Using with Existing Project Dependencies

If your main project has its own `pyproject.toml` file, you can add `timeline_viz` as a local dependency:

```toml
# In your main project's pyproject.toml
[tool.poetry.dependencies]
python = ">=3.8"
# Your other dependencies...
timeline_viz = {path = "./timeline_viz", develop = true}
```

Then update your environment:

```bash
uv pip install -e .
```

This ensures that both your main project and the timeline_viz library maintain consistent dependencies.