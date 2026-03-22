"""Generate example promtest charts for documentation.

Run from the timeline_viz directory:
    python examples/gen_charts.py
"""
import os
import sys

# Ensure we can import from the parent (timeline_viz) directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import matplotlib
matplotlib.use('Agg')
from promtest import parse_promtest_string, plot_promtest

OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'images')

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
plot_promtest(groups, show_plot=False, output_file=os.path.join(OUT_DIR, 'promtest_example_1.png'),
             title='Example: InstanceDown Alert Test', dpi=150, figsize=(14, 8))
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
plot_promtest(groups2, show_plot=False, output_file=os.path.join(OUT_DIR, 'promtest_example_2.png'),
             title='Example: Multi-Series with Gaps & Stale Markers', dpi=150, figsize=(14, 9))
print("Saved promtest_example_2.png")
