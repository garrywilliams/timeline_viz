# Timeline Visualization

A Python library for creating timeline visualizations from timestamp data — CSV files, DataFrames, or **Prometheus test files**.

![Example Timeline](images/timeline1.png)

## Features

- Create clean, professional timeline visualizations from any timestamp data
- Handle time gaps with broken timeline display
- Process multiple entities from CSV files
- Auto-detect timestamp columns based on naming patterns
- **Visualise Prometheus promtool unit-test files** — series values, eval checkpoints, and alert checks on a relative time axis
- Customizable appearance with color schemes
- Command-line interface for non-programmers
- Python API for integration into notebooks and applications

## Installation

```bash
# Using uv (recommended)
uv pip install -e ".[test]"

# Or from source
git clone https://github.com/yourusername/timeline_viz.git
cd timeline_viz
uv pip install -e .
```

## Quick Start

### CSV / DataFrame Timelines

```bash
# CLI — auto-detect timestamp columns
timeline-viz data.csv --detect-timestamps --output-dir timelines

# CLI — specify columns explicitly
timeline-viz data.csv --timestamp-columns created_at updated_at completed_at
```

```python
from timeline_viz import plot_timeline, plot_multiple_timelines

# Single entity
import pandas as pd
df = pd.read_csv("data.csv")
plot_timeline(df.iloc[0],
              timestamp_columns=['created_at', 'updated_at', 'completed_at'],
              entity_id="12345")

# Multiple entities
plot_multiple_timelines("data.csv",
                        timestamp_columns=['created_at', 'updated_at'],
                        id_column='entity_id',
                        output_dir="timeline_images")
```

### Prometheus Test Timelines

Visualise `promtool` unit-test YAML files — see series values change over time, where evaluations happen, and when alerts fire.

```bash
# CLI
timeline-viz my_rules_test.yml --promtest
timeline-viz my_rules_test.yml --promtest --output-dir images --no-show
```

```python
from timeline_viz import parse_promtest_file, plot_promtest

groups = parse_promtest_file("my_rules_test.yml")
plot_promtest(groups, output_file="promtest_timeline.png")
```

![Promtest Example](images/promtest_example_1.png)

Charts are self-documenting — each subplot shows the metric name and raw notation, value labels appear at transition points, eval/alert vertical lines are labelled, and a legend strip at the bottom explains all marker types.

> **Full guide:** [PROMTEST.md](PROMTEST.md) — notation reference, worked examples, and all parameters.

## How It Works

### CSV Timelines

Timestamps are plotted as labeled points along a horizontal axis. When time gaps exceed a threshold, the timeline is broken into segments with slash markers indicating the breaks. Events are labeled with both their name and timestamp, displayed in alternating positions above and below the timeline.

### Promtest Timelines

Prometheus test files define metric series as values over discrete time steps (e.g. one value per minute). The library:

1. Parses the YAML and **expands the compact notation** (`1+2x5` → `1, 3, 5, 7, 9, 11`)
2. Plots each `input_series` as a **step chart** on its own subplot
3. Draws **vertical markers** at `eval_time` checkpoints
4. Shows **alert check points** with firing/pending status
5. Labels the x-axis with **relative time offsets** (`0s`, `1m`, `2m`, …)

## Key Parameters

### CSV Mode

| Parameter | Description |
|-----------|-------------|
| `timestamp_columns` | Columns containing timestamp data to visualise |
| `id_column` | Column that uniquely identifies each entity |
| `threshold_days` | Time gap (in days) that triggers a timeline break |
| `entity_name` | Type name for titles (e.g. "Patient", "Order") |
| `label_mappings` | Custom display names for timestamp columns |
| `color_scheme` | Dictionary of colour overrides |

### Promtest Mode

| Parameter | Description |
|-----------|-------------|
| `figsize` | Figure dimensions `(width, height)` in inches |
| `title` | Custom figure title |
| `color_scheme` | Override colours (see [PROMTEST.md](PROMTEST.md#colour-scheme)) |
| `output_file` | Save to PNG |
| `dpi` | Resolution (default 150) |

## Advanced Features

### Automatic Timestamp Detection

The library auto-detects timestamp columns based on:

- Column names ending with `_utc`, `_at`, `_time`, or `_date`
- Column names containing `timestamp` or `datetime`
- Column names starting with `date` or `time`

### Custom Color Schemes

```python
color_scheme = {
    'line': '#0046be',          # Timeline
    'point_edge': '#0046be',    # Point border
    'point_face': '#ffe000',    # Point fill
    'connector': '#0046be',     # Connector lines
    'label_bg': '#f5f5f5',      # Label background
    'label_edge': '#0046be',    # Label border
    'slashes': '#0046be',       # Timeline breaks
    'title': '#0046be'          # Title
}
```

## Requirements

### Runtime Dependencies
- Python 3.8+
- NumPy
- Pandas
- Matplotlib
- PyYAML

### Development Dependencies
- pytest
- pytest-cov
- pre-commit (optional, for git hooks)
