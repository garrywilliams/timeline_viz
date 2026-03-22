import matplotlib
matplotlib.use('Agg')

import pytest
from datetime import timedelta

from timelineviz.promtest import (
    parse_duration,
    expand_values,
    parse_promtest_string,
    plot_promtest,
    _parse_metric_selector,
    _td_to_minutes,
    _format_duration_short,
    SeriesData,
    EvalPoint,
    AlertCheck,
    PromTestGroup,
)


# -----------------------------------------------------------------------
# parse_duration
# -----------------------------------------------------------------------

class TestParseDuration:
    def test_minutes(self):
        assert parse_duration('5m') == timedelta(minutes=5)

    def test_hours_minutes(self):
        assert parse_duration('1h30m') == timedelta(hours=1, minutes=30)

    def test_seconds(self):
        assert parse_duration('90s') == timedelta(seconds=90)

    def test_days(self):
        assert parse_duration('2d') == timedelta(days=2)

    def test_milliseconds(self):
        assert parse_duration('500ms') == timedelta(milliseconds=500)

    def test_full_combo(self):
        assert parse_duration('1d2h3m4s5ms') == timedelta(
            days=1, hours=2, minutes=3, seconds=4, milliseconds=5
        )

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_duration('xyz')

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_duration('')


# -----------------------------------------------------------------------
# expand_values
# -----------------------------------------------------------------------

class TestExpandValues:
    def test_plain_numbers(self):
        assert expand_values('1 2 3') == [1.0, 2.0, 3.0]

    def test_increment(self):
        # 1+2x3 → 1, 3, 5, 7  (4 values)
        assert expand_values('1+2x3') == [1.0, 3.0, 5.0, 7.0]

    def test_decrement(self):
        # 10-2x3 → 10, 8, 6, 4
        assert expand_values('10-2x3') == [10.0, 8.0, 6.0, 4.0]

    def test_repeat(self):
        # 5x3 → 5, 5, 5, 5  (4 values: initial + 3 repeats)
        assert expand_values('5x3') == [5.0, 5.0, 5.0, 5.0]

    def test_missing_single(self):
        assert expand_values('1 _ 3') == [1.0, None, 3.0]

    def test_missing_repeat(self):
        assert expand_values('1 _x3 5') == [1.0, None, None, None, 5.0]

    def test_stale(self):
        assert expand_values('1 stale 3') == [1.0, 'stale', 3.0]

    def test_combined(self):
        # '1+0x6 0 0 0 0 0 0 0 0' → 7 ones then 8 zeros
        result = expand_values('1+0x6 0 0 0 0 0 0 0 0')
        assert result == [1.0] * 7 + [0.0] * 8

    def test_two_patterns(self):
        # '10+10x2 30+20x2' → 10 20 30 30 50 70
        result = expand_values('10+10x2 30+20x2')
        assert result == [10.0, 20.0, 30.0, 30.0, 50.0, 70.0]

    def test_zero_value(self):
        assert expand_values('0') == [0.0]

    def test_float_values(self):
        assert expand_values('1.5 2.5') == [1.5, 2.5]

    def test_negative_start(self):
        assert expand_values('-5+1x2') == [-5.0, -4.0, -3.0]

    def test_invalid_token_raises(self):
        with pytest.raises(ValueError):
            expand_values('not_a_value')

    def test_empty_string(self):
        assert expand_values('') == []
        assert expand_values('  ') == []


# -----------------------------------------------------------------------
# _parse_metric_selector
# -----------------------------------------------------------------------

class TestParseMetricSelector:
    def test_simple_metric(self):
        name, labels = _parse_metric_selector('up')
        assert name == 'up'
        assert labels == {}

    def test_metric_with_labels(self):
        name, labels = _parse_metric_selector('http_requests{method="GET", code="200"}')
        assert name == 'http_requests'
        assert labels == {'method': 'GET', 'code': '200'}

    def test_metric_with_single_label(self):
        name, labels = _parse_metric_selector('node_cpu{cpu="0"}')
        assert name == 'node_cpu'
        assert labels == {'cpu': '0'}


# -----------------------------------------------------------------------
# parse_promtest_string
# -----------------------------------------------------------------------

SAMPLE_YAML = """\
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


class TestParsePromtestString:
    def test_parse_basic(self):
        groups = parse_promtest_string(SAMPLE_YAML)
        assert len(groups) == 1
        g = groups[0]
        assert g.interval == timedelta(minutes=1)
        assert len(g.series) == 2
        assert len(g.alert_checks) == 1
        assert len(g.eval_points) == 1

    def test_series_values_expanded(self):
        groups = parse_promtest_string(SAMPLE_YAML)
        g = groups[0]
        api = g.series[0]
        # 1+0x14 = 15 ones,  0+0x5 = 6 zeros  → 21 values
        assert len(api.values) == 21
        assert api.values[:15] == [1.0] * 15
        assert api.values[15:] == [0.0] * 6

        web = g.series[1]
        # 1x19 = 20 ones
        assert len(web.values) == 20
        assert all(v == 1.0 for v in web.values)

    def test_series_metadata(self):
        groups = parse_promtest_string(SAMPLE_YAML)
        api = groups[0].series[0]
        assert api.metric == 'up'
        assert api.labels == {'job': 'api'}
        assert api.display_name == 'up{job="api"}'

    def test_eval_point(self):
        groups = parse_promtest_string(SAMPLE_YAML)
        ep = groups[0].eval_points[0]
        assert ep.expr == 'up == 0'
        assert ep.eval_time == timedelta(minutes=16)

    def test_alert_check(self):
        groups = parse_promtest_string(SAMPLE_YAML)
        ac = groups[0].alert_checks[0]
        assert ac.alertname == 'InstanceDown'
        assert ac.eval_time == timedelta(minutes=15)
        assert len(ac.exp_alerts) == 1

    def test_multiple_groups(self):
        yaml_str = """\
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: 'up'
        values: '1x4'
  - interval: 5m
    input_series:
      - series: 'down'
        values: '0x2'
"""
        groups = parse_promtest_string(yaml_str)
        assert len(groups) == 2
        assert groups[0].interval == timedelta(minutes=1)
        assert groups[1].interval == timedelta(minutes=5)


# -----------------------------------------------------------------------
# SeriesData
# -----------------------------------------------------------------------

class TestSeriesData:
    def test_time_offsets(self):
        s = SeriesData(metric='m', labels={}, values=[1, 2, 3],
                       interval=timedelta(minutes=5))
        assert s.time_offsets == [
            timedelta(minutes=0),
            timedelta(minutes=5),
            timedelta(minutes=10),
        ]

    def test_display_name_no_labels(self):
        s = SeriesData(metric='up', labels={}, values=[], interval=timedelta(minutes=1))
        assert s.display_name == 'up'

    def test_display_name_with_labels(self):
        s = SeriesData(metric='up', labels={'job': 'api'},
                       values=[], interval=timedelta(minutes=1))
        assert s.display_name == 'up{job="api"}'


# -----------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------

class TestHelpers:
    def test_td_to_minutes(self):
        assert _td_to_minutes(timedelta(hours=1)) == 60.0
        assert _td_to_minutes(timedelta(minutes=5, seconds=30)) == 5.5

    def test_format_duration_short(self):
        assert _format_duration_short(timedelta(minutes=5)) == '5m'
        assert _format_duration_short(timedelta(hours=1, minutes=30)) == '1h30m'
        assert _format_duration_short(timedelta(seconds=90)) == '1m30s'
        assert _format_duration_short(timedelta(0)) == '0s'


# -----------------------------------------------------------------------
# Visualisation (smoke tests)
# -----------------------------------------------------------------------

class TestPlotPromtest:
    def test_basic_plot(self):
        groups = parse_promtest_string(SAMPLE_YAML)
        results = plot_promtest(groups, show_plot=False)
        assert len(results) == 1
        fig, axs = results[0]
        assert fig is not None
        assert len(axs) >= 2  # at least 2 series subplots
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_series_only(self):
        yaml_str = """\
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: 'metric_a'
        values: '0+1x9'
"""
        groups = parse_promtest_string(yaml_str)
        results = plot_promtest(groups, show_plot=False)
        assert len(results) == 1
        fig, axs = results[0]
        # 1 series, no alerts → 1 row
        assert len(axs) == 1
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_output_file(self, tmp_path):
        groups = parse_promtest_string(SAMPLE_YAML)
        out = str(tmp_path / 'test.png')
        results = plot_promtest(groups, show_plot=False, output_file=out)
        import os
        assert os.path.exists(out)
        import matplotlib.pyplot as plt
        for fig, _ in results:
            plt.close(fig)

    def test_custom_title(self):
        groups = parse_promtest_string(SAMPLE_YAML)
        results = plot_promtest(groups, show_plot=False, title='My Test')
        fig, _ = results[0]
        assert fig._suptitle.get_text() == 'My Test'
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_with_gaps_and_stale(self):
        yaml_str = """\
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: 'metric_b'
        values: '1 _ stale 4 5'
"""
        groups = parse_promtest_string(yaml_str)
        results = plot_promtest(groups, show_plot=False)
        assert len(results) == 1
        import matplotlib.pyplot as plt
        plt.close(results[0][0])

    def test_empty_groups(self):
        results = plot_promtest([], show_plot=False)
        assert results == []
