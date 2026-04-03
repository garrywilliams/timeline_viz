"""Generate example promtest charts for documentation.

Run from the repo root:
    uv run python examples/gen_charts.py
    # or: make example-charts

Writes to ``images/``:

- ``promtest_example_1.png``, ``promtest_example_2.png`` — inline YAML demos
- ``promtest_label_readable.png``, ``promtest_label_multi.png`` — from example fixtures
- ``promtest_alert_panel_demo.png`` — dense Alert Checks labels (interval packing)
- ``promtest_callout_packing.png``, ``promtest_callout_packing_compact.png`` — main-axis
  directional callout packing (``examples/promtest_callout_packing.yml``)
- ``event_log_timeline.png`` — long-format log sample (ERROR/WARN only)
"""

import os

import matplotlib

matplotlib.use("Agg")
from timelineviz.promtest import parse_promtest_file, parse_promtest_string, plot_promtest
from timelineviz.timeline import plot_event_log_timeline

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(REPO_ROOT, "images")
EXAMPLES = os.path.join(REPO_ROOT, "examples")

# Example 1: InstanceDown alert test
yaml1 = """\
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: 'up{job="api"}'
        values: '1+0x14 0+0x5'
      - series: 'up{job="web"}'
        values: '1x19'
    alert_rule_test:
      - eval_time: 15m
        alertname: InstanceDown
        exp_alerts:
          - exp_labels:
              job: api
    promql_expr_test:
      - expr: up == 0
        eval_time: 16m
        exp_samples:
          - labels: 'up{job="api"}'
            value: 0
"""

groups = parse_promtest_string(yaml1)
plot_promtest(
    groups,
    show_plot=False,
    output_file=os.path.join(OUT_DIR, "promtest_example_1.png"),
    title="Example: InstanceDown Alert Test",
    dpi=150,
    figsize=(14, 8),
)
print("Saved promtest_example_1.png")

# Example 2: Multiple series with gaps, stale, and gradual changes
yaml2 = """\
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: 'http_requests_total{method="GET"}'
        values: '0+10x9'
      - series: 'http_requests_total{method="POST"}'
        values: '0+5x4 _ stale 30+5x2'
      - series: 'error_rate'
        values: '0x4 0.5+0.5x3 2x2'
    promql_expr_test:
      - expr: error_rate > 1
        eval_time: 8m
        exp_samples:
          - labels: 'error_rate'
            value: 2
"""

groups2 = parse_promtest_string(yaml2)
plot_promtest(
    groups2,
    show_plot=False,
    output_file=os.path.join(OUT_DIR, "promtest_example_2.png"),
    title="Example: Multi-Series with Gaps & Stale Markers",
    dpi=150,
    figsize=(14, 9),
)
print("Saved promtest_example_2.png")

# Label-layout fixtures (readable)
_demo = parse_promtest_file(os.path.join(EXAMPLES, "promtest_label_demo.yml"))
plot_promtest(
    _demo,
    show_plot=False,
    output_file=os.path.join(OUT_DIR, "promtest_label_readable.png"),
    title="Label layout: readable (dense eval + alert callouts)",
    dpi=150,
    figsize=(14, 9),
    label_layout="readable",
)
print("Saved promtest_label_readable.png")

_multi = parse_promtest_file(os.path.join(EXAMPLES, "promtest_label_multi.yml"))
plot_promtest(
    _multi,
    show_plot=False,
    output_file=os.path.join(OUT_DIR, "promtest_label_multi.png"),
    title="Label layout: readable (multi checkpoints, one series)",
    dpi=150,
    figsize=(13, 7),
    label_layout="readable",
)
print("Saved promtest_label_multi.png")

# Alert Checks row: many checkpoints per alertname (stacked labels)
_ap = parse_promtest_file(os.path.join(EXAMPLES, "promtest_alert_panel_demo.yml"))
plot_promtest(
    _ap,
    show_plot=False,
    output_file=os.path.join(OUT_DIR, "promtest_alert_panel_demo.png"),
    title="Alert Checks: packed labels (readable)",
    dpi=150,
    figsize=(14, 6),
    label_layout="readable",
)
print("Saved promtest_alert_panel_demo.png")

_cp = parse_promtest_file(os.path.join(EXAMPLES, "promtest_callout_packing.yml"))
plot_promtest(
    _cp,
    show_plot=False,
    output_file=os.path.join(OUT_DIR, "promtest_callout_packing.png"),
    title="Main-axis callouts: directional packing (readable)",
    dpi=150,
    figsize=(14, 7),
    label_layout="readable",
)
print("Saved promtest_callout_packing.png")
plot_promtest(
    _cp,
    show_plot=False,
    output_file=os.path.join(OUT_DIR, "promtest_callout_packing_compact.png"),
    title="Main-axis callouts: directional packing (compact)",
    dpi=150,
    figsize=(13, 6.5),
    label_layout="compact",
)
print("Saved promtest_callout_packing_compact.png")

plot_event_log_timeline(
    os.path.join(EXAMPLES, "incident_log.csv"),
    timestamp_column="ts",
    label_column="message",
    filter_column="level",
    include_values=["ERROR", "WARN"],
    title="Event log (long format): ERROR & WARN only",
    show_plot=False,
    output_file=os.path.join(OUT_DIR, "event_log_timeline.png"),
    dpi=150,
    figsize=(14, 4),
)
print("Saved event_log_timeline.png")
