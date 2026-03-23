"""
Prometheus test file (promtool) parser and timeline visualisation.

Parses promtool unit test YAML files and visualises:
- input_series values over time steps
- eval_time checkpoints (vertical markers)
- Alert firing windows (horizontal range bars)
- Multiple series on one timeline

Time model:
  promtool tests use discrete time steps at a fixed interval (e.g. 1m).
  Series values are specified with expanding notation like '1+2x5', '_x3', 'stale'.
  All times are relative offsets from 0 (or a start_timestamp).
"""

import re
from dataclasses import dataclass, field
from datetime import timedelta
from typing import List, Optional, Sequence, Tuple

import numpy as np
import yaml
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


# ---------------------------------------------------------------------------
# Duration parsing
# ---------------------------------------------------------------------------

_DURATION_RE = re.compile(
    r'^(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?(?:(\d+)ms)?$'
)


def parse_duration(s):
    """Parse a Prometheus duration string (e.g. '5m', '1h30m') into a timedelta."""
    s = s.strip()
    m = _DURATION_RE.match(s)
    if not m:
        raise ValueError(f"Invalid duration: {s!r}")
    days = int(m.group(1) or 0)
    hours = int(m.group(2) or 0)
    minutes = int(m.group(3) or 0)
    seconds = int(m.group(4) or 0)
    milliseconds = int(m.group(5) or 0)
    td = timedelta(days=days, hours=hours, minutes=minutes,
                   seconds=seconds, milliseconds=milliseconds)
    if td == timedelta(0) and s != '0s' and s != '0ms':
        raise ValueError(f"Invalid duration: {s!r}")
    return td


# ---------------------------------------------------------------------------
# Series-value expanding notation
# ---------------------------------------------------------------------------

_EXPAND_RE = re.compile(
    r'^'
    r'(?P<value>[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)'  # numeric value
    r'(?:'
    r'  (?P<op>[+-])(?P<step>[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)' # +/-step
    r')?'
    r'(?:x(?P<repeat>\d+))?'  # xN repeat
    r'$',
    re.VERBOSE,
)


def expand_values(notation):
    """Expand a promtool series ``values`` string into a list of floats / None / 'stale'.

    Each element in the returned list corresponds to one interval step.

    Notation rules (space-separated tokens):
      * plain number            → single sample
      * ``a+bxN`` / ``a-bxN``  → a, a±b, a±2b, … (N+1 samples total)
      * ``axN``                 → a repeated N+1 times
      * ``_``                   → missing sample (None)
      * ``_xN``                 → N missing samples
      * ``stale``               → stale marker (string ``'stale'``)

    Returns list[float | None | str].
    """
    tokens = notation.strip().split()
    result = []
    for token in tokens:
        # --- missing / gap ---
        if token == '_':
            result.append(None)
            continue
        m_gap = re.match(r'^_x(\d+)$', token)
        if m_gap:
            result.extend([None] * int(m_gap.group(1)))
            continue

        # --- stale ---
        if token.lower() == 'stale':
            result.append('stale')
            continue

        # --- numeric expanding ---
        m = _EXPAND_RE.match(token)
        if m:
            value = float(m.group('value'))
            op = m.group('op')
            step = float(m.group('step')) if m.group('step') else 0.0
            repeat = int(m.group('repeat')) if m.group('repeat') is not None else 0

            if op is None and m.group('repeat') is not None:
                # shorthand  axN  →  a repeated N+1 times
                result.extend([value] * (repeat + 1))
            elif op is None:
                # plain number
                result.append(value)
            else:
                sign = 1.0 if op == '+' else -1.0
                for i in range(repeat + 1):
                    result.append(value + sign * step * i)
            continue

        raise ValueError(f"Cannot parse series value token: {token!r}")
    return result


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SeriesData:
    """One input_series from a promtool test."""
    metric: str
    labels: dict
    values: list          # list[float | None | 'stale']
    interval: timedelta
    raw_values: str = ''  # original notation string e.g. '1+0x14 0+0x5'

    @property
    def time_offsets(self):
        """Return list of timedelta offsets for each sample."""
        return [self.interval * i for i in range(len(self.values))]

    @property
    def display_name(self):
        if self.labels:
            label_str = ', '.join(f'{k}="{v}"' for k, v in self.labels.items()
                                  if k != '__name__')
            if label_str:
                return f'{self.metric}{{{label_str}}}'
        return self.metric


@dataclass
class EvalPoint:
    """A promql_expr_test evaluation checkpoint."""
    expr: str
    eval_time: timedelta
    expected_results: list  # raw from yaml


@dataclass
class AlertCheck:
    """An alert_rule_test checkpoint."""
    alertname: str
    eval_time: timedelta
    exp_alerts: list       # raw from yaml
    for_duration: Optional[timedelta] = None


@dataclass
class PromTestGroup:
    """One test group from the YAML file."""
    interval: timedelta
    series: list           # list[SeriesData]
    eval_points: list      # list[EvalPoint]
    alert_checks: list     # list[AlertCheck]
    name: str = ''


# ---------------------------------------------------------------------------
# YAML parser
# ---------------------------------------------------------------------------

_METRIC_RE = re.compile(
    r'^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)'
    r'(?:\{(?P<labels>[^}]*)\})?$'
)


def _parse_metric_selector(selector):
    """Parse 'metric_name{label1="val1", label2="val2"}' into (name, dict)."""
    m = _METRIC_RE.match(selector.strip())
    if not m:
        return selector.strip(), {}
    name = m.group('name')
    labels = {}
    if m.group('labels'):
        for pair in m.group('labels').split(','):
            pair = pair.strip()
            if '=' not in pair:
                continue
            k, v = pair.split('=', 1)
            labels[k.strip()] = v.strip().strip('"').strip("'")
    return name, labels


def _parse_doc(doc):
    """Parse an already-loaded YAML document into PromTestGroup objects."""
    global_interval = parse_duration(doc.get('evaluation_interval', '1m'))
    groups = []

    for test_entry in doc.get('tests', []):
        interval = parse_duration(test_entry['interval']) if 'interval' in test_entry else global_interval

        series_list = []
        for s in test_entry.get('input_series', []):
            metric_name, labels = _parse_metric_selector(s['series'])
            raw = s['values']
            vals = expand_values(raw)
            series_list.append(SeriesData(
                metric=metric_name,
                labels=labels,
                values=vals,
                interval=interval,
                raw_values=raw,
            ))

        eval_points = []
        for e in test_entry.get('promql_expr_test', []):
            eval_points.append(EvalPoint(
                expr=e['expr'],
                eval_time=parse_duration(e['eval_time']),
                expected_results=e.get('exp_samples', e.get('exp_result', [])),
            ))

        alert_checks = []
        for a in test_entry.get('alert_rule_test', []):
            alert_checks.append(AlertCheck(
                alertname=a['alertname'],
                eval_time=parse_duration(a['eval_time']),
                exp_alerts=a.get('exp_alerts', []),
            ))

        groups.append(PromTestGroup(
            interval=interval,
            series=series_list,
            eval_points=eval_points,
            alert_checks=alert_checks,
            name=test_entry.get('name', ''),
        ))

    return groups


def parse_promtest_file(path):
    """Parse a promtool unit-test YAML file.

    Returns a list of PromTestGroup.
    """
    with open(path) as f:
        doc = yaml.safe_load(f)
    return _parse_doc(doc)


def parse_promtest_string(yaml_string):
    """Parse a promtool unit-test YAML string (convenience for testing).

    Returns a list of PromTestGroup.
    """
    doc = yaml.safe_load(yaml_string)
    return _parse_doc(doc)


# ---------------------------------------------------------------------------
# Visualisation helpers
# ---------------------------------------------------------------------------

def _td_to_minutes(td):
    """Convert timedelta to float minutes."""
    return td.total_seconds() / 60.0


def _format_duration_short(td):
    """Format a timedelta as a compact string like '5m', '1h30m'."""
    total_s = int(td.total_seconds())
    if total_s == 0:
        return '0s'
    parts = []
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    if h:
        parts.append(f'{h}h')
    if m:
        parts.append(f'{m}m')
    if s:
        parts.append(f'{s}s')
    return ''.join(parts)


def find_gap_clusters(sorted_anchors: np.ndarray, gap_threshold: float) -> List[np.ndarray]:
    """Split sorted 1-D anchor positions into clusters when successive gap > threshold.

    Used to break promtest timelines across long idle gaps (same idea as CSV
    ``threshold_days``, but axis is minutes).

    Parameters
    ----------
    sorted_anchors : np.ndarray
        Sorted unique time positions (e.g. minutes).
    gap_threshold : float
        If consecutive anchors differ by more than this, start a new cluster.

    Returns
    -------
    list of np.ndarray
        One array of anchor positions per cluster.
    """
    a = np.asarray(sorted_anchors, dtype=float)
    if a.size <= 1:
        return [a] if a.size == 1 else []
    clusters = []
    start = 0
    for i in range(a.size - 1):
        if a[i + 1] - a[i] > gap_threshold:
            clusters.append(a[start : i + 1])
            start = i + 1
    clusters.append(a[start:])
    return clusters


def _x_windows_from_gap_clusters(
    anchors: Sequence[float],
    gap_threshold: float,
    x_max: float,
    interval_min: float,
) -> List[Tuple[float, float]]:
    """Turn clustered anchors into (x_lo, x_hi) plot windows with padding."""
    arr = np.sort(np.unique(np.asarray(anchors, dtype=float)))
    if arr.size == 0:
        return [(0.0, float(x_max))]
    clusters = find_gap_clusters(arr, gap_threshold)
    windows = []
    for c in clusters:
        mn, mx = float(np.min(c)), float(np.max(c))
        span = max(mx - mn, interval_min * 0.5)
        pad = max(span * 0.08, interval_min * 0.5)
        x_lo = max(0.0, mn - pad)
        x_hi = min(float(x_max), mx + pad)
        if x_lo > x_hi:
            x_lo, x_hi = x_hi, x_lo
        windows.append((x_lo, x_hi))
    return windows


def _indices_covering_x_window(xs: Sequence[float], x_lo: float, x_hi: float) -> range:
    """Index range into monotonic ``xs`` for step plots spanning [x_lo, x_hi]."""
    if not xs:
        return range(0, 0)
    xs = list(xs)
    lo_i = 0
    while lo_i < len(xs) and xs[lo_i] < x_lo:
        lo_i += 1
    if lo_i > 0:
        lo_i -= 1
    hi_i = len(xs) - 1
    while hi_i >= 0 and xs[hi_i] > x_hi:
        hi_i -= 1
    if hi_i < len(xs) - 1 and hi_i >= 0:
        hi_i += 1
    if lo_i > hi_i:
        return range(0, 0)
    return range(lo_i, hi_i + 1)


def _promtest_label_layout_validate(layout: str) -> str:
    allowed = ('readable', 'legacy', 'compact')
    if layout not in allowed:
        raise ValueError(f'label_layout must be one of {allowed}, not {layout!r}')
    return layout


def _annotate_transitions(
    ax, xs, ys, color, *, label_layout: str = 'readable', min_x_gap: Optional[float] = None,
):
    """Value labels at step transitions; optional minimum x-gap to reduce overlap."""
    layout = _promtest_label_layout_validate(label_layout)
    prev_val = None
    candidates = []
    for i, (x, y) in enumerate(zip(xs, ys)):
        show = False
        if i == 0:
            show = True
        elif y != prev_val:
            show = True
        elif i == len(xs) - 1:
            show = True
        if show:
            candidates.append((x, y, i == 0, i == len(xs) - 1))
        prev_val = y

    if layout == 'legacy' or not candidates:
        final = [(c[0], c[1]) for c in candidates]
    else:
        if min_x_gap is None:
            min_x_gap = 1e-6
        final = []
        last_x = -1e30
        for x, y, is_first, is_last in sorted(candidates, key=lambda t: t[0]):
            if is_first or is_last:
                final.append((x, y))
                last_x = x
            elif x - last_x >= min_x_gap:
                final.append((x, y))
                last_x = x

    fs = 6 if layout == 'compact' else 7
    for k, (x, y) in enumerate(final):
        if layout == 'legacy':
            xytext, va = (0, 8), 'bottom'
        else:
            if k % 2 == 0:
                xytext, va = (0, 10), 'bottom'
            else:
                xytext, va = (0, -14), 'top'
        if y == int(y):
            val_str = str(int(y))
        else:
            val_str = f'{y:.2g}'
        ax.annotate(
            val_str, (x, y),
            textcoords='offset points', xytext=xytext,
            ha='center', va=va, fontsize=fs,
            color=color, fontweight='bold', alpha=0.85,
        )


def _annotate_eval_lines(ax, annotations, cs, *, label_layout: str = 'readable'):
    """Labels for eval/alert vertical lines; stagger when layout is not legacy."""
    layout = _promtest_label_layout_validate(label_layout)
    ann_sorted = sorted(annotations, key=lambda t: t[0])
    max_chars = 28 if layout == 'compact' else 40
    fontsize = 6 if layout == 'compact' else 7

    for i, (et, label, kind) in enumerate(ann_sorted):
        if kind == 'eval':
            text = f'eval: {label}'
            colour = cs['eval_line']
        else:
            text = f'alert: {label}'
            colour = cs['alert_firing']

        if len(text) > max_chars:
            text = text[: max_chars - 3] + '...'

        time_str = _format_duration_short(timedelta(minutes=et))
        text = f'{text}\n@ {time_str}'

        if layout == 'legacy':
            ax.annotate(
                text, (et, 1.0),
                xycoords=('data', 'axes fraction'),
                textcoords='offset points', xytext=(4, -4),
                ha='left', va='top', fontsize=fontsize, color=colour,
                fontweight='bold', alpha=0.9,
                bbox=dict(boxstyle='round,pad=0.25', fc='white',
                          ec=colour, alpha=0.85, linewidth=0.7),
            )
        else:
            row = i % 6
            y_frac = 1.0 + row * 0.036
            ha = 'left' if i % 2 == 0 else 'right'
            off_x = 8 if ha == 'left' else -8
            ax.annotate(
                text, (et, y_frac),
                xycoords=('data', 'axes fraction'),
                textcoords='offset points', xytext=(off_x, -2 - row),
                ha=ha, va='bottom', fontsize=fontsize, color=colour,
                fontweight='bold', alpha=0.9,
                bbox=dict(boxstyle='round,pad=0.25', fc='white',
                          ec=colour, alpha=0.85, linewidth=0.7),
            )


def _add_promtest_column_slashes(fig, bottom_axes_row, slash_color: str) -> None:
    """Draw slash markers between adjacent column axes (figure coordinates)."""
    n = len(bottom_axes_row)
    if n < 2:
        return
    for j in range(n - 1):
        right_pos = bottom_axes_row[j].get_position().x1
        left_pos = bottom_axes_row[j + 1].get_position().x0
        mid_pos = (right_pos + left_pos) / 2
        y_center = 0.5
        slash_height = 0.05
        slash_gap = 0.015
        for offset in [-slash_gap / 2, slash_gap / 2]:
            x_mid = mid_pos + offset
            slash = plt.Line2D(
                [x_mid - slash_height / 6, x_mid + slash_height / 6],
                [y_center - slash_height / 2, y_center + slash_height / 2],
                transform=fig.transFigure,
                color=slash_color,
                linewidth=2.5,
                solid_capstyle='round',
                clip_on=False,
                zorder=10,
            )
            fig.add_artist(slash)


# ---------------------------------------------------------------------------
# Main plot function
# ---------------------------------------------------------------------------

PROMTEST_COLOR_SCHEME = {
    'series_colors': [
        '#0046be', '#e6194b', '#3cb44b', '#f58231',
        '#911eb4', '#42d4f4', '#f032e6', '#bfef45',
    ],
    'eval_line': '#e6194b',
    'alert_pending': '#ffc107',
    'alert_firing': '#dc3545',
    'grid': '#e0e0e0',
    'background': '#fafafa',
    'text': '#333333',
    'stale_marker': '#999999',
    'missing_marker': '#cccccc',
    'slashes': '#0046be',
}


def _draw_promtest_time_column(
    column_axes,
    group,
    x_lo: float,
    x_hi: float,
    x_max: float,
    cs: dict,
    eval_annotations: list,
    interval_min: float,
    set_xlabel: bool,
    label_layout: str = 'readable',
) -> None:
    """Draw one horizontal time segment (column) of a promtest figure."""
    n_series = len(group.series)
    has_alerts = bool(group.alert_checks)

    ann_in = [(et, lab, k) for et, lab, k in eval_annotations
              if x_lo - 1e-9 <= et <= x_hi + 1e-9]

    x_pad_col = max((x_hi - x_lo) * 0.08, interval_min * 0.5)
    xlim_lo = x_lo - x_pad_col
    xlim_hi = x_hi + x_pad_col

    for si, series in enumerate(group.series):
        ax = column_axes[si]
        color = cs['series_colors'][si % len(cs['series_colors'])]
        xs, ys = [], []
        stale_xs = []
        gap_xs = []
        for vi, val in enumerate(series.values):
            t = _td_to_minutes(series.interval * vi)
            if val is None:
                gap_xs.append(t)
            elif val == 'stale':
                stale_xs.append(t)
            else:
                xs.append(t)
                ys.append(val)

        idx = _indices_covering_x_window(xs, x_lo, x_hi)
        xs_s = [xs[i] for i in idx] if xs else []
        ys_s = [ys[i] for i in idx] if ys else []

        if xs_s:
            ax.step(xs_s, ys_s, where='post', color=color, linewidth=1.5,
                    zorder=3)
            ax.plot(xs_s, ys_s, 'o', color=color, markersize=5, zorder=4)

        stale_in = [t for t in stale_xs if x_lo <= t <= x_hi]
        if stale_in:
            ax.plot(stale_in, [0] * len(stale_in), 'x',
                    color=cs['stale_marker'], markersize=8,
                    markeredgewidth=2, zorder=4)

        gap_in = [t for t in gap_xs if x_lo <= t <= x_hi]
        if gap_in:
            ax.plot(gap_in, [0] * len(gap_in), 's',
                    color=cs['missing_marker'], markersize=6,
                    markerfacecolor='none', markeredgewidth=1.5,
                    zorder=4)

        for ep in group.eval_points:
            et = _td_to_minutes(ep.eval_time)
            if x_lo - 1e-9 <= et <= x_hi + 1e-9:
                ax.axvline(x=et, color=cs['eval_line'], linestyle='--',
                           linewidth=1.2, alpha=0.7, zorder=2)

        for ac in group.alert_checks:
            et = _td_to_minutes(ac.eval_time)
            if x_lo - 1e-9 <= et <= x_hi + 1e-9:
                ax.axvline(x=et, color=cs['alert_firing'], linestyle=':',
                           linewidth=1.2, alpha=0.6, zorder=2)

        ax.set_ylabel('value', fontsize=8, color='#888888')
        ax.set_xlim(xlim_lo, xlim_hi)
        ax.grid(True, alpha=0.3, color=cs['grid'])
        ax.set_facecolor(cs['background'])

        subtitle = series.display_name
        if series.raw_values:
            raw_display = series.raw_values
            if len(raw_display) > 60:
                raw_display = raw_display[:57] + '...'
            subtitle += f'    values: {raw_display!r}'
        ax.set_title(subtitle, fontsize=8.5, color=cs['text'],
                     loc='left', fontstyle='italic', pad=4)

        if xs_s and ys_s:
            x0, x1 = ax.get_xlim()
            span = max(x1 - x0, 1e-9)
            if label_layout == 'legacy':
                mgap = 0.0
            else:
                mgap = max(span * 0.035, interval_min * 1.2)
                if label_layout == 'compact':
                    mgap *= 1.65
            _annotate_transitions(
                ax, xs_s, ys_s, color, label_layout=label_layout, min_x_gap=mgap,
            )

    if ann_in and n_series > 0:
        _annotate_eval_lines(column_axes[0], ann_in, cs, label_layout=label_layout)

    if has_alerts:
        ax_alert = column_axes[-1]
        alert_names = list({ac.alertname for ac in group.alert_checks})
        alert_y = {name: i for i, name in enumerate(alert_names)}

        alert_draw_order = sorted(
            [ac for ac in group.alert_checks
             if x_lo - 1e-9 <= _td_to_minutes(ac.eval_time) <= x_hi + 1e-9],
            key=lambda a: (_td_to_minutes(a.eval_time), alert_y[a.alertname]),
        )
        stack_key_counts = {}

        for ac in alert_draw_order:
            et = _td_to_minutes(ac.eval_time)
            y = alert_y[ac.alertname]
            is_firing = bool(ac.exp_alerts)
            color = cs['alert_firing'] if is_firing else cs['alert_pending']
            marker = 'D' if is_firing else 'o'
            ax_alert.plot(et, y, marker, color=color, markersize=10,
                          zorder=4)
            label_text = 'FIRING' if is_firing else 'no alerts'
            label_full = (
                f'{ac.alertname} @ {_format_duration_short(ac.eval_time)} — {label_text}'
            )
            if label_layout == 'legacy':
                dy = 0
                ha, off_x = 'left', 8
            else:
                sk = (round(et, 5), y)
                stack_key_counts[sk] = stack_key_counts.get(sk, 0) + 1
                k = stack_key_counts[sk] - 1
                dy = k * 12
                ha = 'left' if k % 2 == 0 else 'right'
                off_x = 10 if ha == 'left' else -10
            fs = 7 if label_layout != 'compact' else 6
            if label_layout == 'compact' and len(label_full) > 42:
                label_full = label_full[:39] + '...'
            ax_alert.annotate(
                label_full, (et, y),
                textcoords='offset points', xytext=(off_x, dy),
                ha=ha, va='center', fontsize=fs, color=color,
                fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', fc='white',
                          ec=color, alpha=0.85, linewidth=0.8),
            )

        for ep in group.eval_points:
            et = _td_to_minutes(ep.eval_time)
            if x_lo - 1e-9 <= et <= x_hi + 1e-9:
                ax_alert.axvline(x=et, color=cs['eval_line'], linestyle='--',
                                 linewidth=1.2, alpha=0.7, zorder=2)

        ax_alert.set_yticks(range(len(alert_names)))
        ax_alert.set_yticklabels(alert_names, fontsize=9)
        ax_alert.set_ylim(-0.5, len(alert_names) - 0.5)
        ax_alert.set_xlim(xlim_lo, xlim_hi)
        ax_alert.set_ylabel('', fontsize=8)
        ax_alert.set_title('Alert Checks', fontsize=8.5, color=cs['text'],
                           loc='left', fontstyle='italic', pad=4)
        ax_alert.grid(True, alpha=0.3, color=cs['grid'])
        ax_alert.set_facecolor(cs['background'])

    bottom_ax = column_axes[-1]
    if interval_min > 0:
        lo_step = int(np.floor(xlim_lo / interval_min)) * interval_min
        hi_step = int(np.ceil(xlim_hi / interval_min)) * interval_min
        tick_positions = []
        t = lo_step
        while t <= hi_step + interval_min * 0.5:
            if xlim_lo - 1e-9 <= t <= xlim_hi + 1e-9:
                tick_positions.append(t)
            t += interval_min
        if not tick_positions:
            tick_positions = [xlim_lo, xlim_hi]
    else:
        tick_positions = [xlim_lo, xlim_hi]

    bottom_ax.set_xticks(tick_positions)

    def _fmt_tick(x, _pos):
        return _format_duration_short(timedelta(minutes=x))

    bottom_ax.xaxis.set_major_formatter(FuncFormatter(_fmt_tick))
    if set_xlabel:
        bottom_ax.set_xlabel(
            f'Time offset  (interval: {_format_duration_short(group.interval)}, '
            f'each tick = 1 step)',
            fontsize=9, color=cs['text'],
        )


def plot_promtest(groups, figsize=None, show_plot=True, output_file=None,
                  dpi=150, title=None, color_scheme=None,
                  break_gap_minutes=None, label_layout='readable'):
    """Visualise parsed promtool test groups.

    Parameters
    ----------
    groups : list[PromTestGroup]
        As returned by ``parse_promtest_file`` / ``parse_promtest_string``.
    figsize : tuple, optional
        (width, height) in inches.  Auto-sized if None.
    show_plot : bool
        Display interactively.
    output_file : str, optional
        Save PNG to this path.
    dpi : int
        Resolution.
    title : str, optional
        Overall figure title.
    color_scheme : dict, optional
        Override ``PROMTEST_COLOR_SCHEME`` keys.
    break_gap_minutes : float, optional
        If set, split the horizontal axis into multiple panels when the gap
        between consecutive **anchor** times exceeds this many minutes.
        Anchors are ``0``, ``x_max``, and every eval / alert time. Matches the
        spirit of CSV ``threshold_days`` breaks. If ``None`` (default), one
        continuous x-axis (original behaviour).
    label_layout : str, default ``'readable'``
        How to place eval/alert callouts and step value labels to limit overlap:
        ``'readable'`` (staggered rows, spaced value labels, stacked alert text),
        ``'compact'`` (stronger truncation and fewer value labels), or
        ``'legacy'`` (original placement).

    Returns
    -------
    list[tuple[plt.Figure, list[plt.Axes]]]
        One (fig, axes) pair per TestGroup. Axes are listed row-major when
        multiple time columns exist (series rows, then columns left-to-right).
    """
    if break_gap_minutes is not None and break_gap_minutes <= 0:
        raise ValueError('break_gap_minutes must be positive when set')
    _promtest_label_layout_validate(label_layout)

    cs = {**PROMTEST_COLOR_SCHEME, **(color_scheme or {})}
    results = []

    for gi, group in enumerate(groups):
        n_series = len(group.series)
        has_alerts = bool(group.alert_checks)
        has_evals = bool(group.eval_points)
        n_rows = max(n_series, 1) + (1 if has_alerts else 0)

        if figsize is None:
            fig_w = max(12, n_series * 2)
            fig_h = max(5, n_rows * 2.5 + 1.2)
        else:
            fig_w, fig_h = figsize

        all_durations = []
        for s in group.series:
            if s.values:
                last = s.interval * (len(s.values) - 1)
                all_durations.append(_td_to_minutes(last))
        for ep in group.eval_points:
            all_durations.append(_td_to_minutes(ep.eval_time))
        for ac in group.alert_checks:
            all_durations.append(_td_to_minutes(ac.eval_time))

        x_max = max(all_durations) if all_durations else 10.0

        eval_annotations = []
        for ep in group.eval_points:
            eval_annotations.append((_td_to_minutes(ep.eval_time), ep.expr, 'eval'))
        for ac in group.alert_checks:
            eval_annotations.append((_td_to_minutes(ac.eval_time), ac.alertname, 'alert'))

        interval_min = _td_to_minutes(group.interval)

        if break_gap_minutes is None:
            windows = [(0.0, float(x_max))]
        else:
            anchors = [0.0, float(x_max)]
            for et, _, _ in eval_annotations:
                anchors.append(float(et))
            windows = _x_windows_from_gap_clusters(
                anchors, break_gap_minutes, x_max, interval_min,
            )

        n_cols = len(windows)
        ratios = [max(w[1] - w[0], interval_min * 2) for w in windows]
        fig_w_scaled = fig_w * (0.65 + 0.35 * n_cols)

        flat_axes = []

        if n_cols == 1:
            fig, axs_1d = plt.subplots(
                n_rows, 1, figsize=(fig_w, fig_h), sharex=True,
                gridspec_kw={'hspace': 0.45},
            )
            if n_rows == 1:
                axs_1d = [axs_1d]
            col_axes = list(axs_1d)
            _draw_promtest_time_column(
                col_axes, group, windows[0][0], windows[0][1], x_max,
                cs, eval_annotations, interval_min, set_xlabel=True,
                label_layout=label_layout,
            )
            flat_axes = col_axes
            bottom_row_for_slash = [col_axes[-1]]
        else:
            fig, axs_grid = plt.subplots(
                n_rows, n_cols,
                figsize=(fig_w_scaled, fig_h),
                sharex=False,
                gridspec_kw={'hspace': 0.45, 'width_ratios': ratios},
            )
            axs_arr = np.asarray(axs_grid)
            if axs_arr.ndim == 1:
                if n_rows == 1:
                    axs_arr = axs_arr.reshape(1, n_cols)
                else:
                    axs_arr = axs_arr.reshape(n_rows, 1)
            axs_grid = axs_arr
            bottom_row_for_slash = []
            for j, (x_lo, x_hi) in enumerate(windows):
                col_axes = [axs_grid[i, j] for i in range(n_rows)]
                _draw_promtest_time_column(
                    col_axes, group, x_lo, x_hi, x_max,
                    cs, eval_annotations, interval_min,
                    set_xlabel=(j == n_cols - 1),
                    label_layout=label_layout,
                )
                bottom_row_for_slash.append(col_axes[-1])
            for i in range(n_rows):
                for j in range(n_cols):
                    flat_axes.append(axs_grid[i, j])

        fig_title = title
        if fig_title is None:
            fig_title = 'Promtest Timeline'
            if group.name:
                fig_title += f' — {group.name}'
            if len(groups) > 1:
                fig_title += f' (group {gi + 1}/{len(groups)})'
        if break_gap_minutes is not None and n_cols > 1:
            fig_title += f'  (time breaks > {break_gap_minutes:g}m)'
        fig.suptitle(fig_title, fontsize=14, fontweight='bold', color=cs['text'],
                     y=0.99)

        _add_legend_key(fig, cs, has_evals, has_alerts,
                        bool(any(s.values and None in s.values for s in group.series)),
                        bool(any(s.values and 'stale' in s.values for s in group.series)))

        top_margin = (
            0.88 if label_layout != 'legacy' and eval_annotations else 0.93
        )
        fig.subplots_adjust(hspace=0.45, top=top_margin, bottom=0.13)

        if n_cols > 1:
            fig.canvas.draw()
            _add_promtest_column_slashes(fig, bottom_row_for_slash, cs['slashes'])

        if output_file:
            suffix = f'_{gi}' if len(groups) > 1 else ''
            out = output_file.replace('.png', f'{suffix}.png') if len(groups) > 1 else output_file
            fig.savefig(out, bbox_inches='tight', dpi=dpi)

        if show_plot:
            if plt.get_backend().lower() in ['tkagg', 'qt5agg', 'macosx', 'wx', 'gtk3agg']:
                plt.show()
        else:
            plt.close(fig)

        results.append((fig, flat_axes))

    return results


def _add_legend_key(fig, cs, has_evals, has_alerts, has_gaps, has_stale):
    """Draw a visual legend strip at the bottom of the figure."""
    items = []
    items.append(('o', cs['series_colors'][0], 'Sample point'))
    items.append(('_step_', cs['series_colors'][0], 'Step line (value held until next sample)'))
    if has_evals:
        items.append(('--', cs['eval_line'], 'Expression eval checkpoint'))
    if has_alerts:
        items.append(('D', cs['alert_firing'], 'Alert FIRING'))
        items.append((':', cs['alert_firing'], 'Alert check time'))
    if has_gaps:
        items.append(('s_empty', cs['missing_marker'], 'Missing sample (gap)'))
    if has_stale:
        items.append(('x', cs['stale_marker'], 'Stale sample'))

    n = len(items)
    if n == 0:
        return

    legend_ax = fig.add_axes([0.05, 0.01, 0.9, 0.04])
    legend_ax.set_xlim(0, n)
    legend_ax.set_ylim(0, 1)
    legend_ax.axis('off')

    for i, (marker, colour, label) in enumerate(items):
        cx = i + 0.15
        cy = 0.5
        if marker == '--':
            legend_ax.plot([cx - 0.08, cx + 0.08], [cy, cy], '--',
                           color=colour, linewidth=1.5)
        elif marker == ':':
            legend_ax.plot([cx - 0.08, cx + 0.08], [cy, cy], ':',
                           color=colour, linewidth=1.5)
        elif marker == '_step_':
            legend_ax.plot([cx - 0.08, cx, cx, cx + 0.08],
                           [cy - 0.15, cy - 0.15, cy + 0.15, cy + 0.15],
                           '-', color=colour, linewidth=1.5)
        elif marker == 's_empty':
            legend_ax.plot(cx, cy, 's', color=colour, markersize=6,
                           markerfacecolor='none', markeredgewidth=1.5)
        else:
            legend_ax.plot(cx, cy, marker, color=colour, markersize=6,
                           markeredgewidth=1.5)
        legend_ax.text(cx + 0.18, cy, label, fontsize=7, va='center',
                       color=cs['text'])
