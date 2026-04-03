# timelineviz

[![PyPI version](https://img.shields.io/pypi/v/timelineviz)](https://pypi.org/project/timelineviz/)
[![Python](https://img.shields.io/pypi/pyversions/timelineviz)](https://pypi.org/project/timelineviz/)
[![CI](https://github.com/garrywilliams/timeline_viz/actions/workflows/ci.yml/badge.svg)](https://github.com/garrywilliams/timeline_viz/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/garrywilliams/timeline_viz/blob/main/LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/garrywilliams/timeline_viz)

Timeline visualisation for CSV data and Prometheus test files.

<!-- Image URLs use raw.githubusercontent.com so they render on PyPI; branch must match default (main). -->
![Example CSV timeline (wide format, with a time-gap break)](https://raw.githubusercontent.com/garrywilliams/timeline_viz/main/images/timeline1.png)

## Features

- Plot event timelines from CSV / DataFrame timestamp data
- **Long-format logs** — one timestamp column across many rows, with optional filters on level / event type (incident-style timelines)
- Handle time gaps with broken timeline display
- Auto-detect timestamp columns based on naming patterns
- **Visualise Prometheus `promtool` unit-test files** — series values, eval checkpoints, and alert checks on a relative time axis
- Customisable colour schemes
- CLI and Python API
- **Optional next step:** use saved PNGs (plus your CSV or milestone list) as input to **multimodal / image-generation LLMs** to produce executive-style infographics — see below

## Installation

```bash
pip install timelineviz

# or with uv
uv add timelineviz
```

Python 3.11 or newer is required.

For development:

```bash
git clone https://github.com/garrywilliams/timeline_viz.git
cd timeline_viz
make install
make precommit-install
```

Run `make` or `make help` for tests, linting, builds, and other tasks. CI, release, and maintainer setup details live in [DEVELOPING.md](https://github.com/garrywilliams/timeline_viz/blob/main/DEVELOPING.md).

## Quick Start

### CSV / DataFrame Timelines

```bash
# Auto-detect timestamp columns
timelineviz data.csv --detect-timestamps --output-dir timelines

# Specify columns explicitly
timelineviz data.csv --timestamp-columns created_at updated_at completed_at

# Read CSV data from stdin
cat data.csv | timelineviz --timestamp-columns created_at updated_at completed_at

# Add more visually staggered label bubbles
timelineviz data.csv --timestamp-columns created_at updated_at completed_at --varying-height
```

```python
from timelineviz import plot_timeline, plot_multiple_timelines

import pandas as pd
df = pd.read_csv("data.csv")

# Single entity
plot_timeline(df.iloc[0],
              timestamp_columns=['created_at', 'updated_at', 'completed_at'],
              entity_id="12345")

# Multiple entities
plot_multiple_timelines("data.csv",
                        timestamp_columns=['created_at', 'updated_at'],
                        id_column='entity_id',
                        output_dir="timeline_images")
```

### Event log (long format)

Use this when each **row** is one event and times live in a **single column** (typical logs). Optionally keep or drop rows using another column (for example `level` or `event_type`) so you can focus on an incident and ignore noise.

```bash
timelineviz examples/incident_log.csv --event-log --log-time-column ts \
  --log-label-column message --log-filter-column level \
  --log-include ERROR WARN --output-dir timelines --no-show

# Pipe log rows straight in via stdin
tail -n 100 logs/development.csv | timelineviz --event-log --log-time-column ts \
  --log-label-column message --log-filter-column level \
  --log-include ERROR WARN --output-dir timelines --no-show
```

Omit the input path or pass `-` to read from stdin. This works for wide CSV mode, `--event-log`, and `--promtest`.

For plain-text logs, `timelineviz` can also parse `kubectl logs --timestamps` output directly in `--event-log` mode:

```bash
kubectl logs -n mara deploy/mara-webhook-server --tail=80 --timestamps \
  | timelineviz --event-log --raw-log-format kubectl \
    --log-include INFO WARN ERROR --output-dir timelines --no-show
```

In raw kubectl mode, `timelineviz` defaults to extracted columns `ts`, `level`, and `message`, so `--log-include` / `--log-exclude` work without any extra preprocessing.

```python
from timelineviz import plot_event_log_timeline

plot_event_log_timeline(
    "incident.csv",
    timestamp_column="ts",
    label_column="message",
    filter_column="level",
    include_values=["ERROR", "WARN"],
    varying_height=True,
    output_file="incident_timeline.png",
    show_plot=False,
)
```

A small sample file is in [`examples/incident_log.csv`](https://github.com/garrywilliams/timeline_viz/blob/main/examples/incident_log.csv).

The diagram below is from that sample, using the CLI flags above (**`ERROR`** and **`WARN`** rows only, `message` as the label):

![Long-format event log timeline (incident_log.csv, ERROR and WARN only)](https://raw.githubusercontent.com/garrywilliams/timeline_viz/main/images/event_log_timeline.png)

For a denser example with more incident points, varying-height label bubbles, and multiple time breaks, see
[`examples/review_event_log_breaks.csv`](https://github.com/garrywilliams/timeline_viz/blob/main/examples/review_event_log_breaks.csv)
rendered with `--varying-height --threshold-days 2`:

![Long-format event log timeline with varying-height labels and multiple time breaks](https://raw.githubusercontent.com/garrywilliams/timeline_viz/main/images/event_log_timeline_breaks.png)

### Prometheus Test Timelines

Visualise `promtool` unit-test YAML files — see series values change over time, where evaluations happen, and when alerts fire.

```bash
timelineviz examples/promtest_label_minimal.yml --promtest
timelineviz examples/promtest_label_minimal.yml --promtest --output-dir images --no-show
```

Replace the path with your own promtool unit-test YAML when needed. Checked-in examples live under [`examples/`](examples/).

```python
from timelineviz import parse_promtest_file, plot_promtest

groups = parse_promtest_file("examples/promtest_label_minimal.yml")
plot_promtest(groups, output_file="promtest_timeline.png")
```

![Promtest example: interval-packed callouts](https://raw.githubusercontent.com/garrywilliams/timeline_viz/main/images/promtest_label_multi.png)

Charts are self-documenting — each subplot shows the metric name and raw notation, value labels appear at transition points, eval/alert vertical lines are labelled, and a legend strip at the bottom explains all marker types.

> **Full guide:** [PROMTEST.md](https://github.com/garrywilliams/timeline_viz/blob/main/PROMTEST.md) — notation reference, worked examples, and all parameters.

## How It Works

### CSV Timelines

**Wide format** (default): each entity is a row; timestamps live in separate columns (for example `created_at`, `updated_at`). Those columns become labelled points on one timeline per entity.

**Long format** (`plot_event_log_timeline` / `--event-log`): many rows share one timestamp column; each row is one point. Filters apply before plotting.

In both cases, when time gaps exceed a threshold, the timeline is broken into segments with slash markers indicating the breaks.

### Promtest Timelines

Prometheus test files define metric series as values over discrete time steps (e.g. one value per minute). The library:

1. Parses the YAML and **expands the compact notation** (`1+2x5` → `1, 3, 5, 7, 9, 11`)
2. Plots each `input_series` as a **step chart** on its own subplot
3. Draws **vertical markers** at `eval_time` checkpoints
4. Shows **alert check points** with firing/pending status
5. Labels the x-axis with **relative time offsets** (`0s`, `1m`, `2m`, …)

Optional **`break_gap_minutes`** / CLI **`--promtest-break-gap`**: when gaps between anchors (`0`, series end, each eval/alert time) exceed that many minutes, the chart splits into **multiple horizontal panels** with slash markers—same idea as CSV **`threshold_days`** breaks. See [PROMTEST.md](https://github.com/garrywilliams/timeline_viz/blob/main/PROMTEST.md) and [`examples/promtest_time_breaks.yml`](https://github.com/garrywilliams/timeline_viz/blob/main/examples/promtest_time_breaks.yml).

## From chart output to executive infographics

`timelineviz` is built for **faithful, technical** timelines (PNG from the CLI or `output_file=` in Python). For **stakeholder decks**, **board summaries**, or **comms**, you can treat that output as **source material** for a second step: a **multimodal or image-focused LLM** (any tool that accepts an image plus a long text brief—e.g. **Nano Banana** or similar) together with:

- The **exported PNG** (or a screenshot of the figure)
- Your **structured facts**: ordered milestones, dates, short business descriptions, KPIs, risks, and the story you want told
- A **detailed creative prompt** (audience, tone, layout, colour rules, and what *not* to invent)

The model can **redesign** the information as an infographic while you **verify** dates, labels, and numbers against your data. The sample below is an **illustrative** executive layout (sample healthcare journey) produced from that kind of workflow—not something `timelineviz` renders by itself.

![Example executive infographic derived from timeline-style data and an LLM brief](https://raw.githubusercontent.com/garrywilliams/timeline_viz/main/images/executive_infographic_example.png)

*Example only: narrative layout, icons, and insight rail were generated for communication design; always validate facts against your source CSV and plots.*

## API Reference

### CSV Mode

| Parameter | Description |
|-----------|-------------|
| `timestamp_columns` | Columns containing timestamp data to visualise |
| `id_column` | Column that uniquely identifies each entity |
| `threshold_days` | Time gap (in days) that triggers a timeline break |
| `varying_height` | Stagger labels above/below the line at varying heights for a more visually layered layout |
| `entity_name` | Type name for titles (e.g. "Patient", "Order") |
| `label_mappings` | Custom display names for timestamp columns |
| `color_scheme` | Dictionary of colour overrides |

### Promtest Mode

| Parameter | Description |
|-----------|-------------|
| `figsize` | Figure dimensions `(width, height)` in inches |
| `title` | Custom figure title |
| `color_scheme` | Override colours (see [PROMTEST.md](https://github.com/garrywilliams/timeline_viz/blob/main/PROMTEST.md#colour-scheme)) |
| `output_file` | Save to PNG |
| `dpi` | Resolution (default 150) |

## License

[MIT](https://github.com/garrywilliams/timeline_viz/blob/main/LICENSE)
