import matplotlib

matplotlib.use("Agg")

from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest

from timelineviz.promtest import (
    SeriesData,
    _add_legend_key,
    _add_promtest_column_slashes,
    _alert_panel_annotation_layout,
    _annotate_eval_lines,
    _annotate_transitions,
    _eval_callout_reserve_inches,
    _format_duration_short,
    _indices_covering_x_window,
    _max_packed_eval_callout_rows,
    _pack_eval_callout_rows,
    _parse_metric_selector,
    _promtest_label_layout_validate,
    _promtest_xtick_minutes,
    _td_to_minutes,
    _x_windows_from_gap_clusters,
    expand_values,
    find_gap_clusters,
    parse_duration,
    parse_promtest_file,
    parse_promtest_string,
    plot_promtest,
)

# -----------------------------------------------------------------------
# parse_duration
# -----------------------------------------------------------------------


class TestParseDuration:
    def test_minutes(self):
        assert parse_duration("5m") == timedelta(minutes=5)

    def test_hours_minutes(self):
        assert parse_duration("1h30m") == timedelta(hours=1, minutes=30)

    def test_seconds(self):
        assert parse_duration("90s") == timedelta(seconds=90)

    def test_days(self):
        assert parse_duration("2d") == timedelta(days=2)

    def test_milliseconds(self):
        assert parse_duration("500ms") == timedelta(milliseconds=500)

    def test_full_combo(self):
        assert parse_duration("1d2h3m4s5ms") == timedelta(
            days=1, hours=2, minutes=3, seconds=4, milliseconds=5
        )

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_duration("xyz")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_duration("")


# -----------------------------------------------------------------------
# expand_values
# -----------------------------------------------------------------------


class TestExpandValues:
    def test_plain_numbers(self):
        assert expand_values("1 2 3") == [1.0, 2.0, 3.0]

    def test_increment(self):
        # 1+2x3 → 1, 3, 5, 7  (4 values)
        assert expand_values("1+2x3") == [1.0, 3.0, 5.0, 7.0]

    def test_decrement(self):
        # 10-2x3 → 10, 8, 6, 4
        assert expand_values("10-2x3") == [10.0, 8.0, 6.0, 4.0]

    def test_repeat(self):
        # 5x3 → 5, 5, 5, 5  (4 values: initial + 3 repeats)
        assert expand_values("5x3") == [5.0, 5.0, 5.0, 5.0]

    def test_missing_single(self):
        assert expand_values("1 _ 3") == [1.0, None, 3.0]

    def test_missing_repeat(self):
        assert expand_values("1 _x3 5") == [1.0, None, None, None, 5.0]

    def test_stale(self):
        assert expand_values("1 stale 3") == [1.0, "stale", 3.0]

    def test_combined(self):
        # '1+0x6 0 0 0 0 0 0 0 0' → 7 ones then 8 zeros
        result = expand_values("1+0x6 0 0 0 0 0 0 0 0")
        assert result == [1.0] * 7 + [0.0] * 8

    def test_two_patterns(self):
        # '10+10x2 30+20x2' → 10 20 30 30 50 70
        result = expand_values("10+10x2 30+20x2")
        assert result == [10.0, 20.0, 30.0, 30.0, 50.0, 70.0]

    def test_zero_value(self):
        assert expand_values("0") == [0.0]

    def test_float_values(self):
        assert expand_values("1.5 2.5") == [1.5, 2.5]

    def test_negative_start(self):
        assert expand_values("-5+1x2") == [-5.0, -4.0, -3.0]

    def test_invalid_token_raises(self):
        with pytest.raises(ValueError):
            expand_values("not_a_value")

    def test_empty_string(self):
        assert expand_values("") == []
        assert expand_values("  ") == []


# -----------------------------------------------------------------------
# _parse_metric_selector
# -----------------------------------------------------------------------


class TestParseMetricSelector:
    def test_simple_metric(self):
        name, labels = _parse_metric_selector("up")
        assert name == "up"
        assert labels == {}

    def test_metric_with_labels(self):
        name, labels = _parse_metric_selector('http_requests{method="GET", code="200"}')
        assert name == "http_requests"
        assert labels == {"method": "GET", "code": "200"}

    def test_metric_with_single_label(self):
        name, labels = _parse_metric_selector('node_cpu{cpu="0"}')
        assert name == "node_cpu"
        assert labels == {"cpu": "0"}

    def test_invalid_selector_returns_stripped_input(self):
        name, labels = _parse_metric_selector(" bad selector ")
        assert name == "bad selector"
        assert labels == {}

    def test_invalid_label_pair_is_ignored(self):
        name, labels = _parse_metric_selector('metric{good="1", bad, other="2"}')
        assert name == "metric"
        assert labels == {"good": "1", "other": "2"}


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
        assert api.metric == "up"
        assert api.labels == {"job": "api"}
        assert api.display_name == 'up{job="api"}'

    def test_eval_point(self):
        groups = parse_promtest_string(SAMPLE_YAML)
        ep = groups[0].eval_points[0]
        assert ep.expr == "up == 0"
        assert ep.eval_time == timedelta(minutes=16)

    def test_alert_check(self):
        groups = parse_promtest_string(SAMPLE_YAML)
        ac = groups[0].alert_checks[0]
        assert ac.alertname == "InstanceDown"
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
        s = SeriesData(metric="m", labels={}, values=[1, 2, 3], interval=timedelta(minutes=5))
        assert s.time_offsets == [
            timedelta(minutes=0),
            timedelta(minutes=5),
            timedelta(minutes=10),
        ]

    def test_display_name_no_labels(self):
        s = SeriesData(metric="up", labels={}, values=[], interval=timedelta(minutes=1))
        assert s.display_name == "up"

    def test_display_name_with_labels(self):
        s = SeriesData(metric="up", labels={"job": "api"}, values=[], interval=timedelta(minutes=1))
        assert s.display_name == 'up{job="api"}'


# -----------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------


class TestHelpers:
    def test_td_to_minutes(self):
        assert _td_to_minutes(timedelta(hours=1)) == 60.0
        assert _td_to_minutes(timedelta(minutes=5, seconds=30)) == 5.5

    def test_format_duration_short(self):
        assert _format_duration_short(timedelta(minutes=5)) == "5m"
        assert _format_duration_short(timedelta(hours=1, minutes=30)) == "1h30m"
        assert _format_duration_short(timedelta(seconds=90)) == "1m30s"
        assert _format_duration_short(timedelta(0)) == "0s"

    def test_pack_eval_callout_rows_empty(self):
        assert _pack_eval_callout_rows([], [], 0.1) == ([], 0)

    def test_pack_eval_callout_rows_well_spaced_one_row(self):
        centers = [2.0, 8.0, 14.0]
        half_w = [0.4, 0.4, 0.4]
        rows, n_rows = _pack_eval_callout_rows(centers, half_w, 0.1)
        assert n_rows == 1
        assert rows == [0, 0, 0]

    def test_pack_eval_callout_rows_overlapping_stacks(self):
        centers = [5.0, 5.2, 5.4]
        half_w = [2.0, 2.0, 2.0]
        rows, n_rows = _pack_eval_callout_rows(centers, half_w, 0.05)
        assert n_rows == 3
        assert len(set(rows)) == 3

    def test_pack_eval_callout_rows_left_anchor_reuses_row(self):
        """Symmetric packing would stack 2m/3m/4m; left-anchored extents let 4m share row 0 with 2m."""
        gap = 0.1
        centers = [2.0, 3.0, 4.0]
        half_w = [0.95, 0.95, 0.95]
        rows, n_rows = _pack_eval_callout_rows(centers, half_w, gap)
        assert n_rows == 2
        assert rows[0] == 0
        assert rows[1] != rows[0]
        assert rows[2] == 0

    def test_alert_panel_annotation_layout(self):
        centers = [2.0, 3.0, 15.0]
        texts = ["AlertX @ 2m — FIRING", "AlertX @ 3m — no alerts", "AlertX @ 15m — FIRING"]
        dys, has, n_tiers = _alert_panel_annotation_layout(
            centers,
            texts,
            7.0,
            0.0,
            25.0,
            12.0,
            1.0,
            label_layout="readable",
        )
        assert len(dys) == 3
        assert len(has) == 3
        assert n_tiers >= 1
        assert max(dys) >= 15.0

    def test_max_packed_eval_callout_rows_multi_fixture(self):
        groups = parse_promtest_file(
            str(Path(__file__).resolve().parents[3] / "examples" / "promtest_label_multi.yml"),
        )
        g = groups[0]
        ann = [(_td_to_minutes(ep.eval_time), ep.expr, "eval") for ep in g.eval_points] + [
            (_td_to_minutes(ac.eval_time), ac.alertname, "alert") for ac in g.alert_checks
        ]
        windows = [(0.0, 14.0)]
        ratios = [14.0]
        n = _max_packed_eval_callout_rows(
            ann,
            "readable",
            windows,
            1.0,
            fig_w_in=14.0,
            width_ratios=ratios,
        )
        assert n < len(ann)

    def test_eval_callout_reserve_inches(self):
        assert _eval_callout_reserve_inches(0, "readable") == 0.0
        r2 = _eval_callout_reserve_inches(2, "readable")
        assert r2 > 0
        assert _eval_callout_reserve_inches(2, "compact") < r2

    def test_promtest_xtick_minutes_skips_negative(self):
        ticks = _promtest_xtick_minutes(-2.0, 8.0, 1.0)
        assert all(t >= 0 for t in ticks)
        assert 0.0 in ticks or min(ticks) >= 0

    def test_promtest_xtick_minutes_fallback(self):
        ticks = _promtest_xtick_minutes(0.5, 0.8, 1.0)
        assert len(ticks) >= 1
        assert all(t >= 0 for t in ticks)

    def test_x_windows_empty_anchors(self):
        assert _x_windows_from_gap_clusters([], 10.0, 12.0, 1.0) == [(0.0, 12.0)]

    def test_x_windows_swap_inverted_window(self):
        windows = _x_windows_from_gap_clusters([5.0], 10.0, 1.0, 1.0)
        assert windows == [(1.0, 4.5)]

    def test_promtest_xtick_minutes_zero_interval(self):
        assert _promtest_xtick_minutes(-1.0, -1.0, 0.0) == [0.0]

    def test_promtest_xtick_minutes_clamp_hi_bump(self):
        assert _promtest_xtick_minutes(-1.0, -1.0, 1.0) == [0.0, 1.0]

    def test_indices_covering_x_window_empty(self):
        assert list(_indices_covering_x_window([], 0.0, 1.0)) == []

    def test_indices_covering_x_window_invalid_range(self):
        assert list(_indices_covering_x_window([1.0, 2.0], 10.0, 0.0)) == []

    def test_alert_panel_annotation_layout_empty(self):
        assert _alert_panel_annotation_layout(
            [], [], 7.0, 0.0, 1.0, 10.0, 1.0, label_layout="readable"
        ) == ([], [], 0)

    def test_annotate_transitions_formats_float_values(self):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        _annotate_transitions(ax, [0.0, 1.0, 2.0], [1.25, 1.25, 2.5], "#000000")
        texts = [text.get_text() for text in ax.texts]
        assert "1.2" in texts
        assert "2.5" in texts
        plt.close(fig)

    def test_annotate_eval_lines_empty(self):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        assert _annotate_eval_lines(ax, [], {"eval_line": "#000", "alert_firing": "#f00"}) == 0
        plt.close(fig)

    def test_add_promtest_column_slashes_single_axis_noop(self):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        _add_promtest_column_slashes(fig, [ax], "#000000")
        plt.close(fig)

    def test_add_legend_key_creates_legend_axis(self):
        import matplotlib.pyplot as plt

        fig = plt.figure()
        _add_legend_key(
            fig,
            {
                "series_colors": ["#000000"],
                "eval_line": "#111111",
                "alert_firing": "#222222",
                "missing_marker": "#333333",
                "stale_marker": "#444444",
                "text": "#555555",
            },
            False,
            False,
            False,
            False,
        )
        assert len(fig.axes) == 1
        plt.close(fig)


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

    def test_tick_density_capped(self):
        groups = parse_promtest_string(SAMPLE_YAML)
        fig, axs = plot_promtest(groups, show_plot=False, max_ticks=4)[0]
        try:
            ticks = axs[0].get_xticks()
            assert len(ticks) <= 5
        finally:
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
        out = str(tmp_path / "test.png")
        results = plot_promtest(groups, show_plot=False, output_file=out)
        import os

        assert os.path.exists(out)
        import matplotlib.pyplot as plt

        for fig, _ in results:
            plt.close(fig)

    def test_custom_title(self):
        groups = parse_promtest_string(SAMPLE_YAML)
        results = plot_promtest(groups, show_plot=False, title="My Test")
        fig, _ = results[0]
        assert fig._suptitle.get_text() == "My Test"
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

    def test_alert_row_multiple_checks_same_name(self):
        yaml_str = """\
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: 'up'
        values: '1x25'
    alert_rule_test:
      - eval_time: 2m
        alertname: InstanceDown
        exp_alerts: []
      - eval_time: 3m
        alertname: InstanceDown
        exp_alerts:
          - exp_labels:
              job: api
      - eval_time: 4m
        alertname: InstanceDown
        exp_alerts: []
      - eval_time: 18m
        alertname: InstanceDown
        exp_alerts: []
"""
        groups = parse_promtest_string(yaml_str)
        results = plot_promtest(groups, show_plot=False, label_layout="readable")
        assert len(results) == 1
        import matplotlib.pyplot as plt

        plt.close(results[0][0])

    def test_empty_groups(self):
        results = plot_promtest([], show_plot=False)
        assert results == []

    def test_label_multi_example_fixture(self, tmp_path):
        repo = Path(__file__).resolve().parents[3]
        yml = repo / "examples" / "promtest_label_multi.yml"
        assert yml.is_file()
        groups = parse_promtest_file(str(yml))
        assert len(groups) == 1
        assert len(groups[0].eval_points) == 4
        assert len(groups[0].alert_checks) == 3
        out = tmp_path / "multi.png"
        plot_promtest(groups, show_plot=False, output_file=str(out), label_layout="readable")
        assert out.is_file()

    def test_multiple_groups_title_suffix(self):
        yaml_str = """\
evaluation_interval: 1m
tests:
  - name: First
    input_series:
      - series: 'a'
        values: '1'
  - name: Second
    input_series:
      - series: 'b'
        values: '2'
"""
        results = plot_promtest(parse_promtest_string(yaml_str), show_plot=False)
        assert len(results) == 2
        assert "(group 1/2)" in results[0][0]._suptitle.get_text()
        assert "(group 2/2)" in results[1][0]._suptitle.get_text()
        import matplotlib.pyplot as plt

        for fig, _ in results:
            plt.close(fig)

    def test_compact_alert_label_truncation(self):
        yaml_str = """\
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: 'up'
        values: '1x5'
    alert_rule_test:
      - eval_time: 2m
        alertname: ExtremelyLongAlertNameThatShouldBeTruncatedInCompactMode
        exp_alerts:
          - exp_labels:
              job: api
"""
        fig, _ = plot_promtest(
            parse_promtest_string(yaml_str), show_plot=False, label_layout="compact"
        )[0]
        texts = [text.get_text() for ax in fig.axes for text in ax.texts]
        assert any(text.endswith("...") for text in texts)
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_raw_values_subtitle_truncation(self):
        yaml_str = """\
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: 'metric'
        values: '1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1'
"""
        fig, _ = plot_promtest(parse_promtest_string(yaml_str), show_plot=False)[0]
        titles = [ax.get_title(loc="left") for ax in fig.axes]
        assert any("..." in title for title in titles)
        import matplotlib.pyplot as plt

        plt.close(fig)


# -----------------------------------------------------------------------
# Time-gap clusters (promtest breaks)
# -----------------------------------------------------------------------


class TestFindGapClusters:
    def test_single_point(self):
        c = find_gap_clusters(np.array([5.0]), 10.0)
        assert len(c) == 1
        assert list(c[0]) == [5.0]

    def test_no_break(self):
        c = find_gap_clusters(np.array([0.0, 5.0, 10.0]), 30.0)
        assert len(c) == 1
        assert list(c[0]) == [0.0, 5.0, 10.0]

    def test_break_middle(self):
        c = find_gap_clusters(np.array([0.0, 5.0, 52.0, 54.0]), 40.0)
        assert len(c) == 2
        assert list(c[0]) == [0.0, 5.0]
        assert list(c[1]) == [52.0, 54.0]


class TestXWindowsFromGapClusters:
    def test_two_windows(self):
        w = _x_windows_from_gap_clusters([0, 5, 52, 54], 40, 54, 1.0)
        assert len(w) == 2
        assert w[0][0] <= 0
        assert w[0][1] <= 10
        assert w[1][0] >= 50
        assert w[1][1] <= 54


YAML_SPARSE_EVAL = """\
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: 's'
        values: '0+0x49 1+0x4'
    promql_expr_test:
      - expr: a
        eval_time: 5m
      - expr: b
        eval_time: 52m
"""


class TestPlotPromtestBreakGap:
    def test_single_panel_when_threshold_large(self):
        groups = parse_promtest_string(YAML_SPARSE_EVAL)
        results = plot_promtest(groups, show_plot=False, break_gap_minutes=500)
        fig, axs = results[0]
        n_series = len(groups[0].series)
        assert len(axs) == n_series
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_multi_panel_when_threshold_small(self):
        groups = parse_promtest_string(YAML_SPARSE_EVAL)
        results = plot_promtest(groups, show_plot=False, break_gap_minutes=40)
        fig, axs = results[0]
        n_series = len(groups[0].series)
        assert len(axs) == n_series * 2
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_invalid_break_gap_raises(self):
        groups = parse_promtest_string(YAML_SPARSE_EVAL)
        with pytest.raises(ValueError, match="break_gap"):
            plot_promtest(groups, show_plot=False, break_gap_minutes=0)
        with pytest.raises(ValueError, match="break_gap"):
            plot_promtest(groups, show_plot=False, break_gap_minutes=-1)

    def test_label_layout_variants_smoke(self):
        groups = parse_promtest_string(SAMPLE_YAML)
        for layout in ("readable", "legacy", "compact"):
            fig, axs = plot_promtest(groups, show_plot=False, label_layout=layout)[0]
            assert fig is not None
            import matplotlib.pyplot as plt

            plt.close(fig)

    def test_invalid_label_layout_raises(self):
        groups = parse_promtest_string(SAMPLE_YAML)
        with pytest.raises(ValueError, match="label_layout"):
            plot_promtest(groups, show_plot=False, label_layout="nope")


class TestLabelLayoutValidate:
    def test_ok(self):
        assert _promtest_label_layout_validate("readable") == "readable"

    def test_bad(self):
        with pytest.raises(ValueError):
            _promtest_label_layout_validate("wide")
