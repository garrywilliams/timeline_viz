"""timelineviz — Timelines, swimlanes and Mermaid diagrams from CSVs, logs and Prometheus test files.

Create timeline charts from any timestamp data, or visualise promtool
unit-test YAML files with annotated step charts.

Quick start::

    from timelineviz import plot_timeline, plot_multiple_timelines

    import pandas as pd
    df = pd.read_csv("events.csv")
    plot_timeline(df.iloc[0], ['created_at', 'updated_at', 'completed_at'])

    # Long-format logs (one timestamp column, many rows)
    from timelineviz import plot_event_log_timeline
    plot_event_log_timeline("incident.csv", "ts", label_column="message",
                            filter_column="level", include_values=["ERROR", "WARN"])

    # Build a Timeline yourself, then render it
    from timelineviz import timeline_from_wide, render_timeline
    render_timeline(timeline_from_wide(df.iloc[0]), output_file="t.svg", show_plot=False)

    # Prometheus test files
    from timelineviz import parse_promtest_file, plot_promtest
    groups = parse_promtest_file("rules_test.yml")
    plot_promtest(groups)
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("timelineviz")
except PackageNotFoundError:
    __version__ = "0.0.0.dev0"

from timelineviz.model import (
    Event,
    Timeline,
    timeline_from_event_log,
    timeline_from_wide,
    timeline_from_wide_entities,
)
from timelineviz.promtest import (
    expand_values,
    find_gap_clusters,
    parse_duration,
    parse_promtest_file,
    parse_promtest_string,
    plot_promtest,
)
from timelineviz.render_mermaid import to_mermaid
from timelineviz.render_mpl import render_swimlanes, render_timeline
from timelineviz.timeline import (
    find_clusters,
    format_timestamp,
    plot_event_log_timeline,
    plot_multiple_timelines,
    plot_timeline,
)

__all__ = [
    "__version__",
    "plot_timeline",
    "plot_multiple_timelines",
    "plot_event_log_timeline",
    "Event",
    "Timeline",
    "timeline_from_wide",
    "timeline_from_event_log",
    "render_timeline",
    "render_swimlanes",
    "timeline_from_wide_entities",
    "to_mermaid",
    "find_clusters",
    "format_timestamp",
    "parse_promtest_file",
    "parse_promtest_string",
    "plot_promtest",
    "find_gap_clusters",
    "expand_values",
    "parse_duration",
]
