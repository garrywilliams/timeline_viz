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
from typing import Optional

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
}


def plot_promtest(groups, figsize=None, show_plot=True, output_file=None,
                  dpi=150, title=None, color_scheme=None):
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

    Returns
    -------
    list[tuple[plt.Figure, list[plt.Axes]]]
        One (fig, axes) pair per TestGroup.
    """
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

        fig, axs = plt.subplots(
            n_rows, 1, figsize=(fig_w, fig_h), sharex=True,
            gridspec_kw={'hspace': 0.45},
        )
        if n_rows == 1:
            axs = [axs]

        # Determine x-axis extent (in minutes)
        all_durations = []
        for s in group.series:
            if s.values:
                last = s.interval * (len(s.values) - 1)
                all_durations.append(_td_to_minutes(last))
        for ep in group.eval_points:
            all_durations.append(_td_to_minutes(ep.eval_time))
        for ac in group.alert_checks:
            all_durations.append(_td_to_minutes(ac.eval_time))

        x_max = max(all_durations) if all_durations else 10
        x_pad = max(x_max * 0.08, _td_to_minutes(group.interval) * 0.5)

        # Collect eval/alert annotations
        eval_annotations = []
        for ep in group.eval_points:
            eval_annotations.append((_td_to_minutes(ep.eval_time), ep.expr, 'eval'))
        for ac in group.alert_checks:
            eval_annotations.append((_td_to_minutes(ac.eval_time), ac.alertname, 'alert'))

        # --- plot each series ---
        for si, series in enumerate(group.series):
            ax = axs[si]
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

            # Step plot for numeric values
            if xs:
                ax.step(xs, ys, where='post', color=color, linewidth=1.5,
                        zorder=3)
                ax.plot(xs, ys, 'o', color=color, markersize=5, zorder=4)

            # Mark stale samples
            if stale_xs:
                ax.plot(stale_xs, [0] * len(stale_xs), 'x',
                        color=cs['stale_marker'], markersize=8,
                        markeredgewidth=2, zorder=4)

            # Mark missing samples
            if gap_xs:
                ax.plot(gap_xs, [0] * len(gap_xs), 's',
                        color=cs['missing_marker'], markersize=6,
                        markerfacecolor='none', markeredgewidth=1.5,
                        zorder=4)

            # Eval-time vertical lines on every subplot
            for ep in group.eval_points:
                et = _td_to_minutes(ep.eval_time)
                ax.axvline(x=et, color=cs['eval_line'], linestyle='--',
                           linewidth=1.2, alpha=0.7, zorder=2)

            # Alert check vertical lines
            for ac in group.alert_checks:
                et = _td_to_minutes(ac.eval_time)
                ax.axvline(x=et, color=cs['alert_firing'], linestyle=':',
                           linewidth=1.2, alpha=0.6, zorder=2)

            ax.set_ylabel('value', fontsize=8, color='#888888')
            ax.set_xlim(-x_pad, x_max + x_pad)
            ax.grid(True, alpha=0.3, color=cs['grid'])
            ax.set_facecolor(cs['background'])

            # --- Annotation: series title with raw notation ---
            subtitle = series.display_name
            if series.raw_values:
                raw_display = series.raw_values
                if len(raw_display) > 60:
                    raw_display = raw_display[:57] + '...'
                subtitle += f'    values: {raw_display!r}'
            ax.set_title(subtitle, fontsize=8.5, color=cs['text'],
                         loc='left', fontstyle='italic', pad=4)

            # --- Annotation: value at key transition points ---
            if xs and ys:
                _annotate_transitions(ax, xs, ys, color)

        # --- Annotate eval/alert labels at top of first subplot ---
        if eval_annotations and n_series > 0:
            _annotate_eval_lines(axs[0], eval_annotations, cs)

        # --- alert bar chart row ---
        if has_alerts:
            ax_alert = axs[-1]
            alert_names = list({ac.alertname for ac in group.alert_checks})
            alert_y = {name: i for i, name in enumerate(alert_names)}

            for ac in group.alert_checks:
                y = alert_y[ac.alertname]
                et = _td_to_minutes(ac.eval_time)
                is_firing = bool(ac.exp_alerts)
                color = cs['alert_firing'] if is_firing else cs['alert_pending']
                marker = 'D' if is_firing else 'o'
                ax_alert.plot(et, y, marker, color=color, markersize=10,
                              zorder=4)
                label_text = 'FIRING' if is_firing else 'no alerts'
                label_full = f'{ac.alertname} @ {_format_duration_short(ac.eval_time)} — {label_text}'
                ax_alert.annotate(
                    label_full, (et, y),
                    textcoords='offset points', xytext=(8, 0),
                    ha='left', va='center', fontsize=8, color=color,
                    fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', fc='white',
                              ec=color, alpha=0.85, linewidth=0.8),
                )

            for ep in group.eval_points:
                et = _td_to_minutes(ep.eval_time)
                ax_alert.axvline(x=et, color=cs['eval_line'], linestyle='--',
                                 linewidth=1.2, alpha=0.7, zorder=2)

            ax_alert.set_yticks(range(len(alert_names)))
            ax_alert.set_yticklabels(alert_names, fontsize=9)
            ax_alert.set_ylim(-0.5, len(alert_names) - 0.5)
            ax_alert.set_xlim(-x_pad, x_max + x_pad)
            ax_alert.set_ylabel('', fontsize=8)
            ax_alert.set_title('Alert Checks', fontsize=8.5, color=cs['text'],
                               loc='left', fontstyle='italic', pad=4)
            ax_alert.grid(True, alpha=0.3, color=cs['grid'])
            ax_alert.set_facecolor(cs['background'])

        # --- shared x-axis formatting ---
        bottom_ax = axs[-1]
        interval_min = _td_to_minutes(group.interval)

        # place ticks at each interval step
        tick_count = int(x_max / interval_min) + 1 if interval_min > 0 else 1
        tick_positions = [i * interval_min for i in range(tick_count + 1)]
        bottom_ax.set_xticks(tick_positions)

        def _fmt_tick(x, _pos):
            td = timedelta(minutes=x)
            return _format_duration_short(td)

        bottom_ax.xaxis.set_major_formatter(FuncFormatter(_fmt_tick))
        bottom_ax.set_xlabel(
            f'Time offset  (interval: {_format_duration_short(group.interval)}, '
            f'each tick = 1 step)',
            fontsize=9, color=cs['text'])

        # --- title ---
        fig_title = title
        if fig_title is None:
            fig_title = 'Promtest Timeline'
            if group.name:
                fig_title += f' — {group.name}'
            if len(groups) > 1:
                fig_title += f' (group {gi + 1}/{len(groups)})'
        fig.suptitle(fig_title, fontsize=14, fontweight='bold', color=cs['text'],
                     y=0.99)

        # --- legend key (visual guide) at bottom ---
        _add_legend_key(fig, cs, has_evals, has_alerts,
                        bool(any(s.values and None in s.values for s in group.series)),
                        bool(any(s.values and 'stale' in s.values for s in group.series)))

        fig.subplots_adjust(hspace=0.45, top=0.93, bottom=0.13)

        if output_file:
            suffix = f'_{gi}' if len(groups) > 1 else ''
            out = output_file.replace('.png', f'{suffix}.png') if len(groups) > 1 else output_file
            fig.savefig(out, bbox_inches='tight', dpi=dpi)

        if show_plot:
            if plt.get_backend().lower() in ['tkagg', 'qt5agg', 'macosx', 'wx', 'gtk3agg']:
                plt.show()
        else:
            plt.close(fig)

        results.append((fig, list(axs)))

    return results


def _annotate_transitions(ax, xs, ys, color):
    """Add small value labels at points where the value changes."""
    prev_val = None
    for i, (x, y) in enumerate(zip(xs, ys)):
        show = False
        if i == 0:
            show = True
        elif y != prev_val:
            show = True
        elif i == len(xs) - 1:
            show = True

        if show:
            if y == int(y):
                val_str = str(int(y))
            else:
                val_str = f'{y:.2g}'
            ax.annotate(
                val_str, (x, y),
                textcoords='offset points', xytext=(0, 8),
                ha='center', va='bottom', fontsize=7,
                color=color, fontweight='bold', alpha=0.85,
            )
        prev_val = y


def _annotate_eval_lines(ax, annotations, cs):
    """Add rotated labels at the top of the subplot for eval/alert vertical lines."""
    for et, label, kind in annotations:
        if kind == 'eval':
            text = f'eval: {label}'
            colour = cs['eval_line']
        else:
            text = f'alert: {label}'
            colour = cs['alert_firing']

        if len(text) > 40:
            text = text[:37] + '...'

        time_str = _format_duration_short(timedelta(minutes=et))
        text = f'{text}\n@ {time_str}'

        ax.annotate(
            text, (et, 1.0),
            xycoords=('data', 'axes fraction'),
            textcoords='offset points', xytext=(4, -4),
            ha='left', va='top', fontsize=7, color=colour,
            fontweight='bold', alpha=0.9,
            bbox=dict(boxstyle='round,pad=0.25', fc='white',
                      ec=colour, alpha=0.85, linewidth=0.7),
        )


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
