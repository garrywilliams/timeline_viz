"""timelineviz — Timeline visualisation for CSV data and Prometheus test files.

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

    # Prometheus test files
    from timelineviz import parse_promtest_file, plot_promtest
    groups = parse_promtest_file("rules_test.yml")
    plot_promtest(groups)
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("timelineviz")
except PackageNotFoundError:
    __version__ = "0.0.0.dev0"

from timelineviz.timeline import (
    plot_timeline,
    plot_multiple_timelines,
    plot_event_log_timeline,
    find_clusters,
    format_timestamp,
)

from timelineviz.promtest import (
    parse_promtest_file,
    parse_promtest_string,
    plot_promtest,
    expand_values,
    parse_duration,
)

__all__ = [
    "__version__",
    "plot_timeline",
    "plot_multiple_timelines",
    "plot_event_log_timeline",
    "find_clusters",
    "format_timestamp",
    "parse_promtest_file",
    "parse_promtest_string",
    "plot_promtest",
    "expand_values",
    "parse_duration",
]
